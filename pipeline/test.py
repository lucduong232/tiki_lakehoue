import duckdb

con = duckdb.connect("data/warehouse.duckdb")

# Xem có bảng gì
print(con.execute("SHOW TABLES").fetchdf())

# Xem schema của bảng
print(con.execute("DESCRIBE silver_reviews").fetchdf())

# Query với spec đã flatten
print(con.execute("""
    SELECT *
    FROM silver_listing
""").fetchdf())