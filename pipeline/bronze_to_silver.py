import json
import os
from io import BytesIO

import boto3
import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME      = "raw-data"
PREFIX           = "tiki_books"

DUCKDB_PATH = "data/warehouse.duckdb"


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )


def list_parquet_keys(prefix: str) -> list[str]:
    client = get_s3_client()
    resp = client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    return [obj["Key"] for obj in resp.get("Contents", []) if obj["Key"].endswith(".parquet")]


def download_parquet(key: str) -> pd.DataFrame:
    client = get_s3_client()
    resp = client.get_object(Bucket=BUCKET_NAME, Key=key)
    return pd.read_parquet(BytesIO(resp["Body"].read()))


def merge_all_parquet(prefix: str) -> pd.DataFrame:
    """Download và merge tất cả Parquet files trong một prefix."""
    keys = list_parquet_keys(prefix)
    if not keys:
        raise FileNotFoundError(f"Không tìm thấy Parquet nào tại prefix: {prefix}")

    print(f"  Tìm thấy {len(keys)} file(s) tại {prefix}")
    frames = []
    for key in sorted(keys):
        df = download_parquet(key)
        print(f"    ← {key} ({len(df):,} rows)")
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def clean_listing(df: pd.DataFrame) -> pd.DataFrame:
    rows_in = len(df)

    df = (
        df.sort_values("extracted_at", ascending=False)
          .drop_duplicates(subset=["id"], keep="first")
          .reset_index(drop=True)
    )

    def extract_qty(val):
        if pd.isna(val) or val is None:
            return None
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, dict):
            return val.get("value")
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    return parsed.get("value")
                return int(parsed)
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    df["quantity_sold"] = df["quantity_sold"].apply(extract_qty)

    if "list_price" in df.columns:
        df["list_price"] = df["list_price"].apply(lambda x: None if x == 0 else x)

    cols_to_drop = [c for c in ["author_name", "short_description", "inventory_status"] if c in df.columns]
    df = df.drop(columns=cols_to_drop)

    rows_out = len(df)
    print(f"  [listing]  in={rows_in:,} | dedup_out={rows_out:,} | dropped={rows_in - rows_out:,}")
    return df


def _flatten_specifications(spec_json: str) -> dict:
    """
    specifications là list of groups, mỗi group có list attributes.
    Ví dụ: [{"name": "Thông tin chung", "attributes": [{"code": "author", "name": "Tác giả", "value": "..."}]}]
    → {"spec_author": "...", "spec_book_cover": "...", ...}
    """
    result = {}
    if not spec_json:
        return result
    try:
        groups = json.loads(spec_json) if isinstance(spec_json, str) else spec_json
        for group in groups:
            for attr in group.get("attributes", []):
                code = attr.get("code") or attr.get("name", "unknown")
                key = f"spec_{code}".lower().replace(" ", "_")
                result[key] = attr.get("value")
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return result


def clean_detail(df: pd.DataFrame) -> pd.DataFrame:
    rows_in = len(df)

    df = (
        df.sort_values("extracted_at", ascending=False)
          .drop_duplicates(subset=["product_id"], keep="first")
          .reset_index(drop=True)
    )

    spec_expanded = df["specifications"].apply(_flatten_specifications)
    spec_df = pd.DataFrame(spec_expanded.tolist()).fillna(pd.NA)
    df = pd.concat([df.drop(columns=["specifications"]), spec_df], axis=1)

    df["rating_average"] = pd.to_numeric(df["rating_average"], errors="coerce")
    df["review_count"]   = pd.to_numeric(df["review_count"],   errors="coerce").astype("Int64")
    df["price"]          = pd.to_numeric(df["price"],          errors="coerce")
    df["list_price"]     = pd.to_numeric(df["list_price"],     errors="coerce")
    df["list_price"]     = df["list_price"].apply(lambda x: None if x == 0 else x)

    rows_out = len(df)
    print(f"  [detail]   in={rows_in:,} | dedup_out={rows_out:,} | dropped={rows_in - rows_out:,}")
    return df



def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    rows_in = len(df)

    df = df.dropna(subset=["product_id", "review_id"]).reset_index(drop=True)

    df = (
        df.sort_values("extracted_at", ascending=False)
          .drop_duplicates(subset=["review_id"], keep="first")
          .reset_index(drop=True)
    )

    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")

    def parse_dt(val):
        if pd.isna(val) or val is None:
            return None
        try:
            return pd.to_datetime(int(val), unit="s", utc=True)
        except (ValueError, TypeError):
            pass
        try:
            return pd.to_datetime(val, utc=True)
        except Exception:
            return None

    df["created_at"] = df["created_at"].apply(parse_dt)

    rows_out = len(df)
    print(f"  [reviews]  in={rows_in:,} | dedup_out={rows_out:,} | dropped={rows_in - rows_out:,}")
    return df



def write_to_duckdb(listing_df: pd.DataFrame, detail_df: pd.DataFrame, reviews_df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(DUCKDB_PATH)

    tables = {
        "silver_listing": listing_df,
        "silver_detail":  detail_df,
        "silver_reviews": reviews_df,
    }

    for table_name, df in tables.items():
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
        count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"  ✓ {table_name}: {count:,} rows → {DUCKDB_PATH}")

    con.close()


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n=== BRONZE → SILVER ===\n")

    print("[1/4] Merge listing Parquet files ...")
    raw_listing = merge_all_parquet(f"{PREFIX}/listing/")

    print("\n[2/4] Merge detail + reviews Parquet files ...")
    raw_detail  = merge_all_parquet(f"{PREFIX}/detail/")
    raw_reviews = merge_all_parquet(f"{PREFIX}/reviews/")

    print("\n[3/4] Cleaning ...")
    silver_listing = clean_listing(raw_listing)
    silver_detail  = clean_detail(raw_detail)
    silver_reviews = clean_reviews(raw_reviews)

    print("\n[4/4] Ghi vào DuckDB ...")
    write_to_duckdb(silver_listing, silver_detail, silver_reviews)

    print("\n=== XONG ===")
    print(f"  listing : {len(silver_listing):,} sản phẩm")
    print(f"  detail  : {len(silver_detail):,} sản phẩm")
    print(f"  reviews : {len(silver_reviews):,} reviews")
    print(f"  DuckDB  : {DUCKDB_PATH}")


if __name__ == "__main__":
    main()