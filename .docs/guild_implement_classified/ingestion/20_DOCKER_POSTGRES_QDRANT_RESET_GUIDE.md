# 20. Hướng Dẫn Xóa Và Tạo Lại PostgreSQL + Qdrant Từ Đầu

**Last Updated:** 2026-07-05

File này hướng dẫn xóa sạch dữ liệu PostgreSQL và Qdrant hiện tại (container + bind mount data) rồi tạo lại container từ đầu, dùng cho trường hợp cần reset toàn bộ database/vector store trong lúc phát triển (ví dụ: schema đổi lớn, migration bị lỗi không thể fix ngược, hoặc muốn test lại từ trạng thái rỗng).

> **Cảnh báo:** các bước trong file này xóa vĩnh viễn dữ liệu PostgreSQL và Qdrant đang có trên máy. Chỉ chạy khi đã chắc chắn không cần giữ dữ liệu, hoặc đã backup đầy đủ. Xem `Docker.md` mục 11 (Backup và restore PostgreSQL) và mục 12.6 (Xem snapshot Qdrant) nếu cần backup trước.

---

## 1. Cấu Hình Liên Quan (tham chiếu từ `compose.yaml`)

Dự án dùng bind mount, không dùng named volume, nên `docker compose down -v` không xóa được dữ liệu — phải xóa thủ công thư mục trên host:

```yaml
postgres:
  volumes:
    - ./db/postgres:/var/lib/postgresql/data
    - ./database/postgres/init:/docker-entrypoint-initdb.d:ro

qdrant:
  volumes:
    - ./db/qdrant:/qdrant/storage
    - ./db/qdrant_snapshots:/qdrant/snapshots
```

Các lệnh trong file này chạy tại thư mục `chatbot/` (thư mục chứa `compose.yaml`).

---

## 2. Kiểm Tra Trạng Thái Hiện Tại Trước Khi Quyết Định Reset

Chạy các lệnh này trước để biết đang có gì, tránh xóa nhầm dữ liệu còn dùng.

### 2.1. Xem Danh Sách Database Và Schema Trong PostgreSQL

```bash
cd chatbot

# Danh sach database
docker compose exec postgres psql -U "$POSTGRES_USER" -d postgres -c "\l"

# Danh sach schema trong database dang dung
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dn"
```

### 2.2. Xem Danh Sách Bảng (Table) Trong Schema `css`

PostgreSQL không có khái niệm "collection" như Qdrant — đơn vị tương đương là **table** trong schema `css`.

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt css.*"
```

Xem chi tiết cấu trúc một bảng cụ thể (thay `<table_name>`):

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\d css.<table_name>"
```

Xem số dòng hiện có trong từng bảng, để biết bảng nào đang có dữ liệu thực:

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT schemaname, relname AS table_name, n_live_tup AS row_estimate
FROM pg_stat_user_tables
WHERE schemaname = 'css'
ORDER BY relname;
"
```

Kiểm tra Alembic đang ở revision nào (bảng `alembic_version` nằm ngoài schema `css`, ở schema `public`):

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM alembic_version;"
```

### 2.3. Xem Danh Sách Collection Trong Qdrant

```bash
curl http://localhost:6333/collections
```

Kết quả ví dụ khi đã có collection:

```json
{"result":{"collections":[{"name":"document_chunks"}]},"status":"ok","time":0.0}
```

Kết quả khi Qdrant đang rỗng, chưa tạo collection nào:

```json
{"result":{"collections":[]},"status":"ok","time":0.0}
```

### 2.4. Kiểm Tra Một Collection Cụ Thể Đã Tồn Tại Chưa (có thể coi là "schema" của collection)

Thay `<collection_name>` bằng tên collection đang dùng trong project (xem `15_PART_H_QDRANT_VECTORSTORE_GUIDE.md`):

```bash
curl -i http://localhost:6333/collections/<collection_name>
```

Cách đọc kết quả:

```text
HTTP/1.1 200 OK  -> collection da ton tai, response tra ve config: vector size, distance, so points hien co.
HTTP/1.1 404 Not Found -> collection chua duoc tao.
```

Ví dụ response khi collection tồn tại (rút gọn):

```json
{
  "result": {
    "status": "green",
    "vectors_count": 1234,
    "points_count": 1234,
    "config": {
      "params": {
        "vectors": { "size": 1024, "distance": "Cosine" }
      }
    }
  },
  "status": "ok"
}
```

`size` phải khớp với vector dimension của embedder đang dùng (xem `14_PART_G_EMBEDDING_GUIDE.md` — BGE-M3 thường là 1024). Nếu `size` khác, phải xóa và tạo lại collection, không thể sửa trực tiếp.

### 2.5. Xem Danh Sách Snapshot Qdrant Hiện Có

```bash
curl http://localhost:6333/collections/<collection_name>/snapshots
```

Hoặc xem trực tiếp file trên host (bind mount):

```bash
ls -la chatbot/db/qdrant_snapshots/
```

---

## 3. Bước 0: Backup Nếu Cần Giữ Dữ Liệu

Bỏ qua bước này nếu chắc chắn không cần dữ liệu hiện tại.

```bash
cd chatbot

# Backup PostgreSQL ra file SQL
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > backup_ctu_student_service.sql

# Backup snapshot Qdrant cho tung collection (thay <collection_name>)
curl -X POST http://localhost:6333/collections/<collection_name>/snapshots
```

Snapshot Qdrant được lưu trong `./db/qdrant_snapshots` — copy thư mục này ra ngoài trước khi xóa nếu muốn giữ.

---

## 4. Bước 1: Dừng Và Xóa Container

```bash
cd chatbot
docker compose down
```

Kiểm tra không còn container nào của project đang chạy:

```bash
docker compose ps -a
```

---

## 5. Bước 2: Xóa Bind Mount Data Trên Host

**Đây là bước xóa dữ liệu thực sự.** Kiểm tra đúng thư mục trước khi xóa:

```bash
cd chatbot
ls db/
```

Windows Git Bash / macOS / Linux:

```bash
rm -rf db/postgres
rm -rf db/qdrant
rm -rf db/qdrant_snapshots
```

Windows PowerShell (nếu không dùng Git Bash):

```powershell
Remove-Item -Recurse -Force db\postgres
Remove-Item -Recurse -Force db\qdrant
Remove-Item -Recurse -Force db\qdrant_snapshots
```

Xác nhận đã xóa:

```bash
ls db/ 2>/dev/null || echo "da xoa xong, thu muc db/ khong con hoac rong"
```

> Nếu Docker giữ lock trên thư mục và lệnh xóa bị lỗi quyền truy cập, chạy lại `docker compose down` để đảm bảo container đã dừng hoàn toàn, rồi thử xóa lại.

---

## 6. Bước 3: Tạo Lại Container Từ Đầu

```bash
cd chatbot
docker compose up -d postgres qdrant
docker compose ps
```

PostgreSQL container khởi tạo lại schema `css` chỉ khi thư mục `./db/postgres` còn rỗng (dùng Postgres entrypoint init behavior). Vì đã xóa ở Bước 2, lần `up` này sẽ init database mới hoàn toàn với `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` đang khai báo trong `.env`.

Kiểm tra healthy:

```bash
docker compose logs -f postgres qdrant
```

Đợi đến khi thấy PostgreSQL báo `accepting connections` và Qdrant báo `Qdrant HTTP listening`.

---

## 7. Bước 4: Tạo Lại Schema Bằng Alembic

Database mới tạo chưa có bảng nào. Chạy migration từ đầu:

```bash
cd chatbot/backend
alembic upgrade head
```

Kiểm tra kết quả:

```bash
cd chatbot
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt css.*"'
```

Đối chiếu danh sách bảng với schema hiện tại trong `AGENTS.md` (mục "Core database schema")
và `03_SQLALCHEMY_9_TABLES_GUIDE.md`.

---

## 8. Bước 5: Tạo Lại Collection Qdrant

Qdrant mới tạo không còn collection nào. Tạo lại collection theo `15_PART_H_QDRANT_VECTORSTORE_GUIDE.md` (hàm `ensure_collection()`), hoặc chạy script/entrypoint pipeline đang dùng trong project để tự tạo collection khi ingest lần đầu.

Kiểm tra nhanh bằng API:

```bash
curl http://localhost:6333/collections
```

Kết quả mong đợi là danh sách rỗng (`"collections": []`) trước khi ingest lại dữ liệu.

---

## 9. Bước 6: Ingest Lại Dữ Liệu (nếu cần)

Sau khi schema PostgreSQL và collection Qdrant đã sẵn sàng ở trạng thái rỗng, chạy lại pipeline ingestion cho các document cần có trong hệ thống (xem `13_PART_F_PIPELINE_ORCHESTRATION_GUIDE.md`).

---

## 10. Tóm Tắt Trình Tự Lệnh (chạy liên tiếp)

```bash
cd chatbot

# 0. (tuy chon) backup truoc khi xoa

# 1. dung container
docker compose down

# 2. xoa du lieu
rm -rf db/postgres db/qdrant db/qdrant_snapshots

# 3. tao lai container
docker compose up -d postgres qdrant

# 4. tao lai schema
cd backend
alembic upgrade head
cd ..

# 5. kiem tra
docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt css.*"
curl http://localhost:6333/collections
```

---

## 11. Lưu Ý

- Lệnh `docker compose down -v` (xem `Docker.md` mục 26) không cần thiết trong project này vì không dùng named volume — bind mount phải xóa thủ công như Bước 2.
- Không xóa `database/postgres/init/` — đây là thư mục script init được mount read-only vào container, không phải nơi lưu dữ liệu.
- Nếu chỉ cần reset PostgreSQL hoặc chỉ Qdrant (không cần reset cả hai), chạy tương ứng từng phần: chỉ `rm -rf db/postgres` rồi `docker compose up -d postgres` rồi `alembic upgrade head`; hoặc chỉ `rm -rf db/qdrant db/qdrant_snapshots` rồi `docker compose up -d qdrant` rồi tạo lại collection.
- Sau khi reset, mọi giá trị `id` tự tăng (`SERIAL`/`Integer primary_key`) trong PostgreSQL sẽ bắt đầu lại từ 1. Nếu code hoặc test nào đang hard-code id cũ, cần cập nhật lại.
