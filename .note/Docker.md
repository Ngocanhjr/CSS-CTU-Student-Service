# Docker Commands — CTU Student Service


## Mục lục

  - [1. Quy trình khởi động thường dùng](##1-quy-trình-khởi-động-thường-dùng)
- [1. Kiểm tra cú pháp Compose và giá trị biến môi trường sau khi nội suy](#1-kiểm-tra-cú-pháp-compose-và-giá-trị-biến-môi-trường-sau-khi-nội-suy)
- [2. Tạo hoặc cập nhật container và chạy ở chế độ nền](#2-tạo-hoặc-cập-nhật-container-và-chạy-ở-chế-độ-nền)
- [3. Kiểm tra trạng thái container](#3-kiểm-tra-trạng-thái-container)
- [4. Theo dõi log PostgreSQL và Qdrant](#4-theo-dõi-log-postgresql-và-qdrant)
  - [2. Kiểm tra cấu hình và biến môi trường](#2-kiểm-tra-cấu-hình-và-biến-môi-trường)
  - [3. Tạo, chạy, dừng và khởi động lại container](#3-tạo-chạy-dừng-và-khởi-động-lại-container)
  - [4. Kiểm tra trạng thái, log và tài nguyên](#4-kiểm-tra-trạng-thái-log-và-tài-nguyên)
  - [5. Truy cập shell và chạy lệnh trong container](#5-truy-cập-shell-và-chạy-lệnh-trong-container)
- [PostgreSQL](#postgresql)
  - [6. Kiểm tra PostgreSQL có sẵn sàng hay không](#6-kiểm-tra-postgresql-có-sẵn-sàng-hay-không)
  - [7. Kết nối vào PostgreSQL bằng `psql`](#7-kết-nối-vào-postgresql-bằng-psql)
  - [8. Các lệnh `psql` thường dùng](#8-các-lệnh-psql-thường-dùng)
  - [9. Các câu SQL kiểm tra nhanh](#9-các-câu-sql-kiểm-tra-nhanh)
  - [10. Chạy một file SQL](#10-chạy-một-file-sql)
  - [11. Backup và restore PostgreSQL](#11-backup-và-restore-postgresql)
- [Qdrant](#qdrant)
  - [12. Kiểm tra Qdrant](#12-kiểm-tra-qdrant)
- [Flask / FastAPI Backend](#flask-fastapi-backend)
  - [13. Khi bổ sung service backend](#13-khi-bổ-sung-service-backend)
  - [14. Chạy và kiểm tra backend](#14-chạy-và-kiểm-tra-backend)
  - [15. Lệnh dành cho Flask](#15-lệnh-dành-cho-flask)
  - [16. Lệnh dành cho FastAPI](#16-lệnh-dành-cho-fastapi)
  - [17. Quy tắc kết nối giữa các container](#17-quy-tắc-kết-nối-giữa-các-container)
- [Quy trình làm việc đề xuất](#quy-trình-làm-việc-đề-xuất)
  - [18. Khi chỉ muốn chạy dự án hằng ngày](#18-khi-chỉ-muốn-chạy-dự-án-hằng-ngày)
  - [19. Khi sửa code backend](#19-khi-sửa-code-backend)
  - [20. Khi thay đổi file Compose hoặc `.env`](#20-khi-thay-đổi-file-compose-hoặc-env)
- [Xử lý lỗi thường gặp](#xử-lý-lỗi-thường-gặp)
  - [21. Lỗi `role "$POSTGRES_USER" does not exist`](#21-lỗi-role-postgresuser-does-not-exist)
  - [22. Lỗi `role "ct239h" does not exist`](#22-lỗi-role-ct239h-does-not-exist)
  - [23. Container không chạy hoặc bị `unhealthy`](#23-container-không-chạy-hoặc-bị-unhealthy)
  - [24. Lỗi port đã được sử dụng](#24-lỗi-port-đã-được-sử-dụng)
  - [25. Backend không kết nối được PostgreSQL hoặc Qdrant](#25-backend-không-kết-nối-được-postgresql-hoặc-qdrant)
- [Lệnh nguy hiểm cần thận trọng](#lệnh-nguy-hiểm-cần-thận-trọng)
  - [26. Xóa named volume](#26-xóa-named-volume)
  - [27. Xóa toàn bộ dữ liệu PostgreSQL hoặc Qdrant bind mount](#27-xóa-toàn-bộ-dữ-liệu-postgresql-hoặc-qdrant-bind-mount)
  - [28. Xóa collection Qdrant](#28-xóa-collection-qdrant)
- [Tài liệu tham khảo chính thức](#tài-liệu-tham-khảo-chính-thức)

---

Tài liệu này tổng hợp các lệnh Docker Compose thường dùng cho dự án **CTU Student Service** với các service hiện tại:

- `postgres`: PostgreSQL
- `qdrant`: Qdrant Vector Database
- `backend`: service Flask hoặc FastAPI sẽ bổ sung sau này

> Chạy các lệnh tại thư mục chứa file `compose.yaml` hoặc `docker-compose.yml`.
>
> Các ví dụ PostgreSQL hiện dùng:
>
> - User: `ct239h`
> - Database: `ctu_student_service`
>
> Nếu tên service, user, database hoặc port thay đổi, cần thay lại trong lệnh tương ứng.

---

## 1. Quy trình khởi động thường dùng

```bash
# 1. Kiểm tra cú pháp Compose và giá trị biến môi trường sau khi nội suy
docker compose config

# 2. Tạo hoặc cập nhật container và chạy ở chế độ nền
docker compose up -d

# 3. Kiểm tra trạng thái container
docker compose ps

# 4. Theo dõi log PostgreSQL và Qdrant
docker compose logs -f postgres qdrant
```

Dừng theo dõi log bằng:

```text
Ctrl + C
```

`Ctrl + C` chỉ dừng việc theo dõi log, không dừng container khi container đang chạy bằng `docker compose up -d`.

---

## 2. Kiểm tra cấu hình và biến môi trường

### 2.1. Kiểm tra file Compose

```bash
docker compose config
```

Lệnh này giúp phát hiện:

- Lỗi cú pháp YAML.
- Biến môi trường bị thiếu.
- Giá trị thực tế sau khi đọc file `.env`.
- Cấu hình service, network, port và volume sau khi Compose xử lý.

> **Lưu ý bảo mật:** kết quả `docker compose config` có thể hiển thị giá trị đã nội suy từ `.env`, bao gồm mật khẩu. Không đăng công khai toàn bộ kết quả.

### 2.2. Liệt kê các service đã khai báo

```bash
docker compose config --services
```

Kết quả dự kiến ở giai đoạn hiện tại:

```text
postgres
qdrant
```

Sau khi thêm backend:

```text
postgres
qdrant
backend
```

### 2.3. Kiểm tra biến môi trường bên trong container PostgreSQL

```bash
docker compose exec postgres printenv POSTGRES_USER
docker compose exec postgres printenv POSTGRES_DB
```

Không nên in hoặc chia sẻ công khai `POSTGRES_PASSWORD`.

Kiểm tra nhiều biến cùng lúc trên Windows Command Prompt:

```cmd
docker compose exec postgres env | findstr POSTGRES
```

Kiểm tra nhiều biến cùng lúc trên PowerShell:

```powershell
docker compose exec postgres env | Select-String POSTGRES
```

---

## 3. Tạo, chạy, dừng và khởi động lại container

### 3.1. Tạo hoặc cập nhật toàn bộ service

```bash
docker compose up -d
```

### 3.2. Chỉ chạy PostgreSQL và Qdrant

```bash
docker compose up -d postgres qdrant
```

### 3.3. Build lại image rồi chạy

Dùng khi đã sửa `Dockerfile`, `requirements.txt`, `pyproject.toml` hoặc dependency của backend:

```bash
docker compose up -d --build
```

Chỉ build lại backend:

```bash
docker compose up -d --build backend
```

### 3.4. Tải image mới từ registry

```bash
docker compose pull
```

Sau đó cập nhật container:

```bash
docker compose up -d
```

### 3.5. Dừng container nhưng không xóa container

```bash
docker compose stop
```

Chỉ dừng một service:

```bash
docker compose stop postgres
```

### 3.6. Chạy lại container đã dừng

```bash
docker compose start
```

### 3.7. Khởi động lại service

```bash
docker compose restart postgres
docker compose restart qdrant
docker compose restart backend
```

### 3.8. Dừng và xóa container cùng network do Compose tạo

```bash
docker compose down
```

Lệnh này thường **không xóa dữ liệu** nếu PostgreSQL và Qdrant đang lưu bằng bind mount như:

```yaml
volumes:
  - ./database-data/postgres-data:/var/lib/postgresql/data
  - ./database-data/qdrant-data:/qdrant/storage
```

### 3.9. Xóa container không còn tồn tại trong file Compose

```bash
docker compose down --remove-orphans
```

---

## 4. Kiểm tra trạng thái, log và tài nguyên

### 4.1. Xem trạng thái service

```bash
docker compose ps
```

Xem cả container đã dừng:

```bash
docker compose ps -a
```

### 4.2. Xem log toàn bộ service

```bash
docker compose logs
```

### 4.3. Theo dõi log liên tục

```bash
docker compose logs -f
```

### 4.4. Theo dõi log theo service

```bash
docker compose logs -f postgres
docker compose logs -f qdrant
docker compose logs -f backend
```

### 4.5. Chỉ xem 100 dòng log gần nhất

```bash
docker compose logs --tail=100 postgres
docker compose logs --tail=100 qdrant
docker compose logs --tail=100 backend
```

### 4.6. Theo dõi log có timestamp

```bash
docker compose logs -f --timestamps postgres qdrant
```

### 4.7. Xem mức sử dụng CPU và RAM

```bash
docker stats
```

### 4.8. Xem process đang chạy trong các service

```bash
docker compose top
```

### 4.9. Xem image được Compose sử dụng

```bash
docker compose images
```

---

## 5. Truy cập shell và chạy lệnh trong container

### 5.1. Mở shell trong PostgreSQL container

```bash
docker compose exec postgres sh
```

### 5.2. Mở shell trong Qdrant container

```bash
docker compose exec qdrant sh
```

Qdrant image có thể không chứa đầy đủ các tiện ích shell thông thường.

### 5.3. Mở shell trong backend container

```bash
docker compose exec backend sh
```

Nếu image backend có Bash:

```bash
docker compose exec backend bash
```

### 5.4. Chạy một container tạm thời rồi tự xóa

```bash
docker compose run --rm backend python --version
```

`run --rm` phù hợp cho test, migration, script quản trị hoặc tác vụ chạy một lần.

---

# PostgreSQL

## 6. Kiểm tra PostgreSQL có sẵn sàng hay không

```bash
docker compose exec postgres pg_isready -U ct239h -d ctu_student_service
```

Kết quả thành công thường có dạng:

```text
/var/run/postgresql:5432 - accepting connections
```

---

## 7. Kết nối vào PostgreSQL bằng `psql`

### 7.1. Cách đơn giản và ổn định nhất: dùng giá trị trực tiếp (hay sử dụng)

```bash
docker compose exec postgres psql -U ct239h -d ctu_student_service
```

### 7.2. Dùng biến môi trường bên trong container — Windows Command Prompt

```cmd
docker compose exec postgres sh -c "psql -U $POSTGRES_USER -d $POSTGRES_DB"
```

### 7.3. Dùng biến môi trường bên trong container — PowerShell

```powershell
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

### 7.4. Lệnh sai cần tránh

```bash
docker compose exec postgres sh -c "psql -U '$POSTGRES_USER' -d '$POSTGRES_DB'"
```

Dấu nháy đơn bên trong `sh` làm PostgreSQL nhận tên role theo đúng chuỗi `$POSTGRES_USER`, gây lỗi:

```text
FATAL: role "$POSTGRES_USER" does not exist
```

---

## 8. Các lệnh `psql` thường dùng

Sau khi đã vào `psql`:

```sql
-- Xem thông tin kết nối hiện tại
\conninfo

-- Xem danh sách database
\l

-- Kết nối sang database khác
\c ctu_student_service

-- Xem danh sách role/user
\du

-- Xem danh sách schema
\dn

-- Xem table trong schema public
\dt public.*

-- Xem table trong tất cả schema
\dt *.*

-- Xem view trong schema public
\dv public.*

-- Xem index trong schema public
\di public.*

-- Xem sequence trong schema public
\ds public.*

-- Xem extension đã cài
\dx

-- Xem cấu trúc table documents
\d public.documents

-- Xem cấu trúc chi tiết hơn, gồm storage và mô tả
\d+ public.documents

-- Thoát khỏi psql
\q
```

---

## 9. Các câu SQL kiểm tra nhanh

```sql
-- Xem database và user hiện tại
SELECT current_database(), current_user;

-- Liệt kê table trong schema public
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Kiểm tra số dòng của table documents
SELECT COUNT(*) FROM public.documents;

-- Kiểm tra kích thước database hiện tại
SELECT pg_size_pretty(pg_database_size(current_database()));

-- Xem các kết nối đang hoạt động
SELECT pid, usename, datname, client_addr, state, query
FROM pg_stat_activity
ORDER BY pid;
```

---

## 10. Chạy một file SQL

Giả sử có file:

```text
database/postgres/init/001_init_schema.sql
```

Chạy file từ máy host vào PostgreSQL container:

```bash
docker compose exec -T postgres psql -U ct239h -d ctu_student_service < database/postgres/init/001_init_schema.sql
```

Trên Windows Command Prompt, lệnh chuyển hướng `<` hoạt động bình thường.

> Các file được mount vào `/docker-entrypoint-initdb.d` chỉ tự động chạy khi thư mục dữ liệu PostgreSQL còn trống và database được khởi tạo lần đầu. Thêm file SQL sau khi database đã tồn tại sẽ không làm script tự chạy lại.

---

## 11. Backup và restore PostgreSQL

### 11.1. Backup database ra file SQL

```bash
docker compose exec -T postgres pg_dump -U ct239h -d ctu_student_service > backup_ctu_student_service.sql
```

### 11.2. Restore database từ file SQL

```bash
docker compose exec -T postgres psql -U ct239h -d ctu_student_service < backup_ctu_student_service.sql
```

### 11.3. Backup dạng custom format

```bash
docker compose exec -T postgres pg_dump -U ct239h -d ctu_student_service -Fc > backup_ctu_student_service.dump
```

### 11.4. Restore custom format

```bash
docker compose exec -T postgres pg_restore -U ct239h -d ctu_student_service --clean --if-exists < backup_ctu_student_service.dump
```

> `--clean` có thể xóa object hiện có trước khi restore. Chỉ dùng khi đã hiểu tác động.

---

# Qdrant

## 12. Kiểm tra Qdrant

### 12.1. Kiểm tra readiness

```bash
curl http://localhost:6333/readyz
```

Trên PowerShell nên dùng rõ executable:

```powershell
curl.exe http://localhost:6333/readyz
```

### 12.2. Xem danh sách collection

```bash
curl http://localhost:6333/collections
```

### 12.3. Xem danh sách collection và định dạng JSON dễ đọc

```bash
curl -s http://localhost:6333/collections | python -m json.tool
```

### 12.4. Xem chi tiết một collection

Thay `<collection_name>` bằng tên collection thực tế:

```bash
curl http://localhost:6333/collections/<collection_name>
```

Ví dụ:

```bash
curl http://localhost:6333/collections/ctu_document_chunks
```

### 12.5. Kiểm tra collection có tồn tại hay không

```bash
curl http://localhost:6333/collections/<collection_name>/exists
```

### 12.6. Xem snapshot của collection

```bash
curl http://localhost:6333/collections/<collection_name>/snapshots
```

### 12.7. Mở Qdrant Web UI

```text
http://localhost:6333/dashboard
```

Web UI hỗ trợ xem collection, điểm dữ liệu, chạy REST API và quản lý snapshot.

> Qdrant self-hosted mặc định có thể chấp nhận request từ bất kỳ client nào truy cập được tới service. Khi triển khai ngoài máy local, cần bật API key, giới hạn network và không public port `6333` một cách tùy tiện.

---

# Flask / FastAPI Backend

## 13. Khi bổ sung service backend

Giả sử file Compose có service tên `backend`:

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
```

Chỉ dùng `condition: service_healthy` khi service phụ thuộc đã được khai báo `healthcheck`. Tên service có thể là `backend`, `api`, `flask` hoặc `fastapi`. Trong các lệnh bên dưới, thay `backend` nếu dự án dùng tên khác.

---

## 14. Chạy và kiểm tra backend

### 14.1. Build và chạy backend

```bash
docker compose up -d --build backend
```

### 14.2. Xem log backend

```bash
docker compose logs -f --tail=200 backend
```

### 14.3. Khởi động lại backend

```bash
docker compose restart backend
```

### 14.4. Mở shell backend

```bash
docker compose exec backend sh
```

### 14.5. Kiểm tra phiên bản Python

```bash
docker compose exec backend python --version
```

### 14.6. Chạy test

```bash
docker compose exec backend pytest -q
```

Hoặc chạy trong container tạm thời:

```bash
docker compose run --rm backend pytest -q
```

---

## 15. Lệnh dành cho Flask

### 15.1. Xem danh sách route Flask

```bash
docker compose exec backend flask --app app routes
```

Nếu app factory nằm ở module khác, thay `app` bằng đường dẫn module thực tế.

### 15.2. Chạy migration với Flask-Migrate

Chỉ dùng khi dự án đã cấu hình Flask-Migrate:

```bash
docker compose exec backend flask --app app db current
docker compose exec backend flask --app app db upgrade
docker compose exec backend flask --app app db downgrade
```

### 15.3. Kiểm tra health endpoint từ máy host

Nếu Flask expose port `5000`:

```bash
curl http://localhost:5000/health
```

---

## 16. Lệnh dành cho FastAPI

### 16.1. Kiểm tra FastAPI đã cài hay chưa

```bash
docker compose exec backend python -c "import fastapi; print(fastapi.__version__)"
```

### 16.2. Chạy migration với Alembic

```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
docker compose exec backend alembic history
```

### 16.3. Kiểm tra health endpoint từ máy host

Nếu FastAPI expose port `8000`:

```bash
curl http://localhost:8000/health
```

Mở Swagger UI:

```text
http://localhost:8000/docs
```

---

## 17. Quy tắc kết nối giữa các container

Từ máy host Windows:

```text
PostgreSQL: localhost:<POSTGRES_PORT>
Qdrant:     localhost:6333
Backend:    localhost:5000 hoặc localhost:8000
```

Từ bên trong backend container:

```text
PostgreSQL host: postgres
PostgreSQL port: 5432
Qdrant host:     qdrant
Qdrant port:     6333
```

Ví dụ biến môi trường backend:

```env
DATABASE_URL=postgresql://ct239h:<password>@postgres:5432/ctu_student_service
QDRANT_URL=http://qdrant:6333
```

> Trong container backend, `localhost` trỏ về chính backend container, không trỏ về PostgreSQL hoặc Qdrant container.

### 17.1. Kiểm tra backend có kết nối được PostgreSQL hay không

```bash
docker compose exec backend python -c "import socket; socket.create_connection(('postgres', 5432), 5); print('PostgreSQL connection OK')"
```

### 17.2. Kiểm tra backend có kết nối được Qdrant hay không

```bash
docker compose exec backend python -c "import socket; socket.create_connection(('qdrant', 6333), 5); print('Qdrant connection OK')"
```

---

# Quy trình làm việc đề xuất

## 18. Khi chỉ muốn chạy dự án hằng ngày

```bash
docker compose up -d
docker compose ps
docker compose logs -f --tail=100 postgres qdrant
```

Sau khi có backend:

```bash
docker compose up -d
docker compose ps
docker compose logs -f --tail=100 backend postgres qdrant
```

---

## 19. Khi sửa code backend

Nếu source code được bind mount vào container và backend có chế độ reload:

```bash
docker compose restart backend
```

Nếu sửa dependency hoặc Dockerfile:

```bash
docker compose up -d --build backend
```

Nếu muốn build lại hoàn toàn không dùng cache:

```bash
docker compose build --no-cache backend
docker compose up -d backend
```

---

## 20. Khi thay đổi file Compose hoặc `.env`

```bash
docker compose config
docker compose up -d
```

Nếu service chưa nhận cấu hình mới:

```bash
docker compose up -d --force-recreate
```

Chỉ recreate backend:

```bash
docker compose up -d --force-recreate backend
```

---

# Xử lý lỗi thường gặp

## 21. Lỗi `role "$POSTGRES_USER" does not exist`

Nguyên nhân: câu lệnh dùng dấu nháy đơn làm shell không mở rộng biến môi trường.

Lệnh sai:

```bash
docker compose exec postgres sh -c "psql -U '$POSTGRES_USER' -d '$POSTGRES_DB'"
```

Lệnh đúng trên Windows Command Prompt:

```cmd
docker compose exec postgres sh -c "psql -U $POSTGRES_USER -d $POSTGRES_DB"
```

Hoặc dùng giá trị trực tiếp:

```bash
docker compose exec postgres psql -U ct239h -d ctu_student_service
```

---

## 22. Lỗi `role "ct239h" does not exist`

Nguyên nhân thường gặp: thư mục dữ liệu PostgreSQL đã được khởi tạo trước đó bằng user khác. Việc sửa `POSTGRES_USER` trong `.env` không tự tạo lại role trên database cũ.

Kiểm tra giá trị user và database mà container hiện đang nhận:

```bash
docker compose exec postgres printenv POSTGRES_USER
docker compose exec postgres printenv POSTGRES_DB
```

Nếu cluster cũ được khởi tạo bằng user khác, cần kết nối bằng user ban đầu để tạo thêm role mới, hoặc khởi tạo lại database. Biến `POSTGRES_USER` mới không tự thay đổi role trong cluster đã tồn tại.

Nếu dữ liệu chưa quan trọng và muốn khởi tạo lại hoàn toàn:

1. Backup dữ liệu nếu cần.
2. Chạy `docker compose down`.
3. Xóa đúng thư mục bind mount PostgreSQL trên máy host.
4. Chạy lại `docker compose up -d`.

> Không xóa thư mục dữ liệu khi chưa chắc chắn rằng không cần giữ dữ liệu.

---

## 23. Container không chạy hoặc bị `unhealthy`

```bash
docker compose ps -a
docker compose logs --tail=200 postgres
docker compose logs --tail=200 qdrant
docker compose logs --tail=200 backend
```

Kiểm tra cấu hình:

```bash
docker compose config
```

Khởi động lại service lỗi:

```bash
docker compose restart <service_name>
```

---

## 24. Lỗi port đã được sử dụng

Xem container nào đang dùng port:

```bash
docker ps
```

Trên Windows, kiểm tra process dùng port `5432`:

```cmd
netstat -ano | findstr :5432
```

Kiểm tra port `6333`:

```cmd
netstat -ano | findstr :6333
```

Giải pháp:

- Dừng ứng dụng đang dùng port.
- Đổi port phía host trong `.env` hoặc `compose.yaml`.
- Giữ nguyên port bên trong container nếu không có lý do đặc biệt để thay đổi.

Ví dụ:

```yaml
ports:
  - "5433:5432"
```

Khi đó máy host kết nối `localhost:5433`, nhưng backend container vẫn kết nối `postgres:5432`.

---

## 25. Backend không kết nối được PostgreSQL hoặc Qdrant

Kiểm tra các lỗi thường gặp:

- Backend đang dùng `localhost` thay vì `postgres` hoặc `qdrant`.
- PostgreSQL hoặc Qdrant chưa healthy.
- Sai user, password, database hoặc port.
- Backend chưa nằm cùng Compose network.
- `.env` mới chưa được áp dụng vào container.

Lệnh kiểm tra:

```bash
docker compose ps
docker compose logs --tail=200 backend postgres qdrant
docker compose exec backend printenv DATABASE_URL
docker compose exec backend printenv QDRANT_URL
```

Không chia sẻ công khai giá trị `DATABASE_URL` nếu URL chứa mật khẩu.

---

# Lệnh nguy hiểm cần thận trọng

## 26. Xóa named volume

```bash
docker compose down -v
```

Lệnh này xóa named volume do Compose quản lý và có thể làm mất dữ liệu database.

Nếu đang dùng bind mount, thư mục dữ liệu trên máy host thường vẫn còn, nhưng không nên dựa vào điều này để thay thế backup.

## 27. Xóa toàn bộ dữ liệu PostgreSQL hoặc Qdrant bind mount

Ví dụ các thư mục:

```text
database-data/postgres-data
database-data/qdrant-data
```

Xóa các thư mục này đồng nghĩa với xóa dữ liệu database tương ứng. Chỉ thực hiện khi:

- Đã backup dữ liệu cần thiết.
- Chắc chắn muốn khởi tạo lại từ đầu.
- Đã chạy `docker compose down` trước đó.

## 28. Xóa collection Qdrant

```bash
curl -X DELETE http://localhost:6333/collections/<collection_name>
```

Lệnh này xóa collection và vector data bên trong collection. Không dùng trong quy trình kiểm tra thông thường.

---

# Tài liệu tham khảo chính thức

- Docker Compose CLI: https://docs.docker.com/reference/cli/docker/compose/
- Docker Compose `up`: https://docs.docker.com/reference/cli/docker/compose/up/
- Docker Compose `down`: https://docs.docker.com/reference/cli/docker/compose/down/
- Docker Compose file reference: https://docs.docker.com/reference/compose-file/
- PostgreSQL Official Docker Image: https://hub.docker.com/_/postgres
- Qdrant API Reference: https://api.qdrant.tech/api-reference
- Qdrant Collections: https://qdrant.tech/documentation/manage-data/collections/
- Qdrant Web UI: https://qdrant.tech/documentation/web-ui/
- Qdrant Security: https://qdrant.tech/documentation/security/
- Flask deployment: https://flask.palletsprojects.com/en/stable/deploying/
