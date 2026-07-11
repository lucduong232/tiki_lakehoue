
import argparse
import json
import os
import time
from datetime import datetime
from io import BytesIO

import boto3
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Config ────────────────────────────────────────────────────────────────────

CATEGORY_ID   = 8322       
DEFAULT_PAGES = 20            
REVIEWS_PER_PRODUCT = 20       
SLEEP_LISTING = 1.0            
SLEEP_DETAIL  = 1.5           
TIMEOUT       = 15

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME      = "raw-data"
PREFIX           = "tiki_books"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Referer":         "https://tiki.vn/",
}
print('cc')

def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def upload_parquet(df: pd.DataFrame, key: str):
    """Serialize DataFrame → Parquet rồi upload lên MinIO."""
    buf = BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)

    client = get_s3_client()
    client.put_object(Bucket=BUCKET_NAME, Key=key, Body=buf.getvalue())
    print(f"  ✓ Uploaded {len(df):,} rows → s3://{BUCKET_NAME}/{key}")


def list_parquet_keys(prefix: str) -> list[str]:
    """Liệt kê tất cả Parquet key trong bucket theo prefix."""
    client = get_s3_client()
    resp = client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", []) if obj["Key"].endswith(".parquet")]


def download_parquet(key: str) -> pd.DataFrame:
    """Download một Parquet file từ MinIO về DataFrame."""
    client = get_s3_client()
    resp = client.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_parquet(BytesIO(resp["Body"].read()))


def sanitize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Chuyển dict/list thành JSON string để Parquet không bị lỗi."""
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
            df[col] = df[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x
            )
    return df


# ─── Pass 1: Listing ───────────────────────────────────────────────────────────

def fetch_listing(num_pages: int = DEFAULT_PAGES) -> list[dict]:
    """
    Crawl danh sách sản phẩm từ Tiki listing API.
    Trả về list raw product dict.
    """
    all_products = []

    for page in range(1, num_pages + 1):
        url = (
            "https://tiki.vn/api/personalish/v1/blocks/listings"
            f"?limit=40&include=advertisement&aggregations=2"
            f"&version=home-persionalized&category={CATEGORY_ID}&page={page}"
        )
        print(f"  [listing] page {page}/{num_pages} ...", end=" ")

        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                print(f"HTTP {resp.status_code} — dừng.")
                break

            items = resp.json().get("data", [])
            if not items:
                print("hết data — dừng.")
                break

            all_products.extend(items)
            print(f"{len(items)} sản phẩm (tổng: {len(all_products)})")

        except requests.RequestException as e:
            print(f"lỗi: {e} — dừng.")
            break

        time.sleep(SLEEP_LISTING)

    return all_products


def run_listing_pass(num_pages: int = DEFAULT_PAGES):
    print("\n=== PASS 1: LISTING ===")
    products = fetch_listing(num_pages)
    if not products:
        print("Không có data listing.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    df = pd.DataFrame(products)
    df["extracted_at"] = ts
    df = sanitize_for_parquet(df)

    key = f"{PREFIX}/listing/listing_{ts}.parquet"
    upload_parquet(df, key)
    print(f"\nListing pass xong: {len(df):,} sản phẩm.")


# ─── Pass 2: Detail + Reviews ──────────────────────────────────────────────────

def fetch_product_detail(product_id: int) -> dict | None:
    """
    GET /api/v2/products/{product_id}
    Trả về fields quan trọng: description, specifications, images, categories, ...
    """
    url = f"https://tiki.vn/api/v2/products/{product_id}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            d = resp.json()
            return {
                "product_id":      d.get("id"),
                "name":            d.get("name"),
                "description":     d.get("description"),          # HTML dài
                "short_description": d.get("short_description"),
                "price":           d.get("price"),
                "list_price":      d.get("list_price"),
                "discount_rate":   d.get("discount_rate"),
                "rating_average":  d.get("rating_average"),
                "review_count":    d.get("review_count"),
                "inventory_status": d.get("inventory_status"),
                "specifications":  json.dumps(                    # list of spec groups
                    d.get("specifications", []), ensure_ascii=False
                ),
                "images":          json.dumps(
                    [img.get("base_url") for img in d.get("images", [])],
                    ensure_ascii=False
                ),
                "categories":      json.dumps(
                    d.get("categories", {}), ensure_ascii=False
                ),
                "url_key":         d.get("url_key"),
                "sku":             d.get("sku"),
                "extracted_at":    datetime.now().strftime("%Y%m%d_%H%M%S"),
            }
        else:
            print(f"    [detail] {product_id} → HTTP {resp.status_code}")
            return None
    except requests.RequestException as e:
        print(f"    [detail] {product_id} → lỗi: {e}")
        return None


def fetch_product_reviews(product_id: int, num_pages: int = REVIEWS_PER_PRODUCT) -> list[dict]:
    """
    GET /api/v2/reviews?product_id={id}&page={p}&limit=20&sort=newest
    Trả về list review dict đã được flatten.
    """
    reviews = []
    for page in range(1, num_pages + 1):
        url = (
            f"https://tiki.vn/api/v2/reviews"
            f"?product_id={product_id}&page={page}&limit=20&sort=newest"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                break

            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            for r in items:
                reviews.append({
                    "review_id":    r.get("id"),
                    "product_id":   product_id,
                    "rating":       r.get("rating"),
                    "title":        r.get("title"),
                    "content":      r.get("content"),
                    "thank_count":  r.get("thank_count"),
                    "created_at":   r.get("created_at"),
                    "reviewer_name": r.get("created_by", {}).get("name") if r.get("created_by") else None,
                    "reviewer_purchased": r.get("created_by", {}).get("purchased") if r.get("created_by") else None,
                    "extracted_at": datetime.now().strftime("%Y%m%d_%H%M%S"),
                })

            # Nếu đã lấy đủ hết reviews thì dừng sớm
            total = data.get("paging", {}).get("total", 0)
            if len(reviews) >= total:
                break

        except requests.RequestException:
            break

        time.sleep(0.5)  # nhẹ tay hơn listing

    return reviews


def get_latest_listing_key() -> str | None:
    """Lấy file listing Parquet mới nhất trong MinIO."""
    keys = list_parquet_keys(f"{PREFIX}/listing/")
    if not keys:
        return None
    return sorted(keys)[-1]  # sort theo tên → mới nhất ở cuối


def run_detail_pass(num_reviews_pages: int = REVIEWS_PER_PRODUCT):
    print("\n=== PASS 2: DETAIL + REVIEWS ===")

    # Đọc listing mới nhất từ MinIO
    listing_key = get_latest_listing_key()
    if not listing_key:
        print("Không tìm thấy listing trong MinIO. Chạy --mode listing trước.")
        return

    print(f"  Đọc listing từ: s3://{BUCKET_NAME}/{listing_key}")
    listing_df = download_parquet(listing_key)
    product_ids = listing_df["id"].dropna().astype(int).unique().tolist()
    print(f"  Tổng {len(product_ids):,} product_id cần crawl detail + reviews.\n")

    all_details = []
    all_reviews = []

    for i, pid in enumerate(product_ids, 1):
        print(f"  [{i:>4}/{len(product_ids)}] product_id={pid}", end=" ")

        # Detail
        detail = fetch_product_detail(pid)
        if detail:
            all_details.append(detail)
            print(f"✓ detail", end=" ")
        else:
            print(f"✗ detail", end=" ")

        # Reviews
        reviews = fetch_product_reviews(pid, num_pages=num_reviews_pages)
        all_reviews.extend(reviews)
        print(f"| {len(reviews)} reviews")

        time.sleep(SLEEP_DETAIL)

        # Checkpoint mỗi 100 sản phẩm — tránh mất hết nếu crash
        if i % 100 == 0:
            _checkpoint(all_details, all_reviews, i)

    # Upload lần cuối
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _upload_detail_reviews(all_details, all_reviews, ts)
    print(f"\nDetail pass xong: {len(all_details):,} detail, {len(all_reviews):,} reviews.")


def _checkpoint(details: list, reviews: list, step: int):
    """Upload checkpoint giữa chừng — an toàn khi crawl lâu."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n  [checkpoint] bước {step} — upload tạm ...")
    _upload_detail_reviews(details, reviews, f"{ts}_ckpt{step}")


def _upload_detail_reviews(details: list, reviews: list, ts: str):
    if details:
        df_detail = pd.DataFrame(details)
        upload_parquet(df_detail, f"{PREFIX}/detail/detail_{ts}.parquet")
    if reviews:
        df_reviews = pd.DataFrame(reviews)
        upload_parquet(df_reviews, f"{PREFIX}/reviews/reviews_{ts}.parquet")


# ─── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tiki Books Crawler")
    parser.add_argument(
        "--mode",
        choices=["listing", "detail", "all"],
        default="all",
        help="listing = chỉ crawl listing | detail = crawl detail+reviews | all = cả hai",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGES,
        help=f"Số trang listing cần crawl (default: {DEFAULT_PAGES}, tối đa ~50)",
    )
    parser.add_argument(
        "--review-pages",
        type=int,
        default=REVIEWS_PER_PRODUCT,
        help=f"Số trang review mỗi sản phẩm (default: {REVIEWS_PER_PRODUCT}, 20 review/page)",
    )
    args = parser.parse_args()

    print(f"Mode: {args.mode} | Pages: {args.pages} | Review pages/product: {args.review_pages}")

    if args.mode in ("listing", "all"):
        run_listing_pass(num_pages=args.pages)

    if args.mode in ("detail", "all"):
        run_detail_pass(num_reviews_pages=args.review_pages)


if __name__ == "__main__":
    main()