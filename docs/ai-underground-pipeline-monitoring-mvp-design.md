# AI 기반 지하배관 상태 모니터링 시스템 MVP 설계서

## 1. 목표와 범위

### 1.1 MVP 목표

AI 기반 지하배관 상태 모니터링 시스템은 지하에 매설된 상수도, 하수도, 가스, 열수송관 등의 관로 상태를 공간 정보와 센서 데이터를 기반으로 통합 관리하고, 이상 징후를 조기에 탐지하여 운영자가 점검, 출동, 보수 의사결정을 빠르게 수행하도록 지원하는 것을 목표로 한다.

MVP는 다음 기능을 실제 개발 가능한 수준으로 제공한다.

- 지도 기반 배관, 맨홀, 밸브, 센서 위치 조회
- 배관 및 센서 메타데이터 관리
- 시계열 센서 데이터 수집, 저장, 조회
- AI 이상 탐지 결과 저장 및 알림 생성
- 운영자 대시보드 및 알림 처리 워크플로우
- 점검 이력, 조치 이력 관리
- 조직, 사용자, 역할 기반 접근 제어

### 1.2 MVP 제외 범위

다음 항목은 MVP 이후 단계에서 확장한다.

- 실시간 제어 명령을 통한 밸브 원격 조작
- 외부 지자체 GIS 시스템과의 양방향 동기화
- 복수 AI 모델 자동 학습 파이프라인
- 모바일 네이티브 앱
- 대규모 스트리밍 처리용 Kafka 클러스터 운영
- 3D 지하시설물 모델링

### 1.3 주요 사용자

| 사용자 | 설명 | 주요 작업 |
| --- | --- | --- |
| 시스템 관리자 | 전체 시스템과 조직, 권한을 관리한다. | 사용자, 조직, 역할, 설정 관리 |
| 관제 관리자 | 관제 정책과 알림 처리 상태를 총괄한다. | 대시보드 확인, 알림 배정, 통계 확인 |
| 관제 운영자 | 일상 관제와 이상 이벤트 대응을 수행한다. | 알림 확인, 이벤트 처리, 점검 요청 |
| 현장 점검자 | 현장 점검 및 조치 내용을 기록한다. | 점검 이력 등록, 사진/메모 업로드 |
| 분석가 | 센서 데이터와 AI 탐지 결과를 검토한다. | 데이터 조회, 모델 결과 검증 |
| 감사자 | 이력과 권한 변경 내역을 조회한다. | 감사 로그 조회 |

## 2. 시스템 아키텍처

### 2.1 논리 아키텍처

```mermaid
flowchart TB
    subgraph Field[현장 계층]
        Sensor[압력/유량/수위/진동/가스 센서]
        Gateway[IoT Gateway]
    end

    subgraph Ingestion[수집 계층]
        MQTT[MQTT Broker]
        Collector[Telemetry Collector]
        BatchImport[CSV/GIS Batch Import]
    end

    subgraph Backend[Backend 계층]
        API[REST API Server]
        Auth[Auth/RBAC Module]
        Alert[Alert Service]
        AI[AI Inference Service]
        Job[Scheduler/Worker]
    end

    subgraph Data[Data 계층]
        PG[(PostgreSQL + PostGIS)]
        TS[(TimescaleDB Hypertables)]
        Object[(Object Storage)]
        Cache[(Redis)]
    end

    subgraph Frontend[Presentation 계층]
        Web[Web Admin/Monitoring Console]
        Map[GIS Map UI]
    end

    Sensor --> Gateway
    Gateway --> MQTT
    MQTT --> Collector
    BatchImport --> API
    Collector --> API
    API --> Auth
    API --> PG
    API --> TS
    API --> Object
    API --> Cache
    AI --> TS
    AI --> PG
    AI --> Alert
    Job --> AI
    Alert --> PG
    Web --> API
    Map --> API
```

### 2.2 컴포넌트 책임

| 컴포넌트 | 책임 | MVP 구현 방식 |
| --- | --- | --- |
| Web Console | 대시보드, 지도, 알림, 점검 이력 UI 제공 | React 또는 Next.js SPA |
| API Server | 인증, 업무 API, 권한 검사, 트랜잭션 처리 | FastAPI 또는 NestJS |
| Telemetry Collector | MQTT 메시지를 검증하고 시계열 테이블에 저장 | API 서버 내 모듈 또는 별도 Python worker |
| AI Inference Service | 센서 데이터 기반 이상 점수와 이상 유형 산출 | Python service, REST/internal job 방식 |
| Alert Service | AI 결과 또는 임계치 위반을 알림으로 변환 | Backend domain service |
| Scheduler/Worker | 주기적 추론, 알림 에스컬레이션, 통계 집계 | Celery/RQ 또는 Nest BullMQ |
| PostgreSQL/PostGIS | 업무 데이터, 공간 데이터, 권한 데이터 저장 | PostgreSQL 16 + PostGIS |
| TimescaleDB | 대용량 센서 시계열 데이터 저장 | PostgreSQL 확장으로 사용 |
| Redis | 세션, 캐시, 작업 큐 브로커 | Redis 7 |
| Object Storage | 점검 사진, 첨부파일 저장 | MinIO |
| MQTT Broker | 현장 게이트웨이 데이터 수신 | Eclipse Mosquitto |

### 2.3 데이터 흐름

#### 센서 데이터 수집 흐름

1. 현장 센서가 게이트웨이에 측정값을 전송한다.
2. 게이트웨이는 MQTT topic `tenants/{tenant_id}/sensors/{sensor_code}/telemetry`로 메시지를 발행한다.
3. Telemetry Collector가 MQTT 메시지를 구독한다.
4. Collector는 센서 식별자, 타임스탬프, 단위, 값 범위, 서명 또는 토큰을 검증한다.
5. 유효한 데이터는 `sensor_readings` hypertable에 저장한다.
6. 임계치 위반 데이터는 즉시 `anomaly_events`와 `alerts` 후보로 전달한다.
7. 배치 AI 추론 작업은 최근 데이터 윈도우를 읽어 이상 점수를 계산한다.

#### 알림 처리 흐름

1. AI 추론 또는 룰 엔진이 이상 이벤트를 생성한다.
2. Alert Service가 심각도, 위치, 배관 중요도, 중복 이벤트 여부를 평가한다.
3. 신규 또는 갱신 알림을 `alerts`에 저장한다.
4. 관제 운영자는 알림을 확인하고 담당자를 배정한다.
5. 현장 점검자는 점검 결과와 조치 내용을 등록한다.
6. 운영자는 알림을 종료하거나 재점검 상태로 변경한다.
7. 모든 상태 변경은 `audit_logs`에 기록한다.

## 3. ERD

```mermaid
erDiagram
    tenants ||--o{ users : has
    tenants ||--o{ assets_pipelines : owns
    tenants ||--o{ sensors : owns
    tenants ||--o{ inspection_tasks : owns

    organizations ||--o{ users : contains
    users ||--o{ user_roles : assigned
    roles ||--o{ user_roles : assigned
    roles ||--o{ role_permissions : has
    permissions ||--o{ role_permissions : grants

    assets_pipelines ||--o{ pipeline_segments : contains
    pipeline_segments ||--o{ sensors : installed_on
    pipeline_segments ||--o{ anomaly_events : occurs_on
    pipeline_segments ||--o{ inspection_tasks : targets

    sensors ||--o{ sensor_readings : emits
    sensors ||--o{ anomaly_events : detects

    anomaly_events ||--o{ alerts : creates
    alerts ||--o{ alert_assignments : assigned
    users ||--o{ alert_assignments : receives
    alerts ||--o{ inspection_tasks : triggers

    inspection_tasks ||--o{ inspection_records : has
    users ||--o{ inspection_records : writes
    inspection_records ||--o{ attachments : includes

    users ||--o{ audit_logs : actor

    tenants {
        uuid id PK
        text name
        text status
        timestamptz created_at
    }

    organizations {
        uuid id PK
        uuid tenant_id FK
        uuid parent_id FK
        text name
    }

    users {
        uuid id PK
        uuid tenant_id FK
        uuid organization_id FK
        text email UK
        text password_hash
        text name
        text status
    }

    roles {
        uuid id PK
        uuid tenant_id FK
        text code
        text name
        boolean is_system
    }

    permissions {
        uuid id PK
        text resource
        text action
        text code UK
    }

    assets_pipelines {
        uuid id PK
        uuid tenant_id FK
        text code UK
        text name
        text pipeline_type
        geometry geom
    }

    pipeline_segments {
        uuid id PK
        uuid pipeline_id FK
        text code UK
        text material
        numeric diameter_mm
        numeric depth_m
        geometry geom
    }

    sensors {
        uuid id PK
        uuid tenant_id FK
        uuid segment_id FK
        text sensor_code UK
        text sensor_type
        text unit
        geometry geom
        text status
    }

    sensor_readings {
        bigint id PK
        uuid sensor_id FK
        timestamptz measured_at
        double value
        jsonb quality
    }

    anomaly_events {
        uuid id PK
        uuid tenant_id FK
        uuid sensor_id FK
        uuid segment_id FK
        text anomaly_type
        numeric score
        text severity
        text status
    }

    alerts {
        uuid id PK
        uuid tenant_id FK
        uuid anomaly_event_id FK
        text title
        text severity
        text status
    }

    inspection_tasks {
        uuid id PK
        uuid tenant_id FK
        uuid alert_id FK
        uuid segment_id FK
        text status
        timestamptz due_at
    }
```

## 4. PostgreSQL/PostGIS 설계

### 4.1 확장 기능

MVP 데이터베이스는 PostgreSQL 기반으로 구성하고 다음 확장을 활성화한다.

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

### 4.2 스키마 분리

| 스키마 | 목적 |
| --- | --- |
| `iam` | 사용자, 조직, 역할, 권한 |
| `asset` | 배관, 구간, 설비, 센서 메타데이터 |
| `telemetry` | 센서 시계열 데이터 |
| `monitoring` | 이상 이벤트, 알림, 점검 업무 |
| `audit` | 감사 로그 |
| `common` | 공통 코드, 파일 메타데이터 |

### 4.3 핵심 테이블 설계

#### `asset.pipelines`

```sql
CREATE TABLE asset.pipelines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES iam.tenants(id),
    code text NOT NULL,
    name text NOT NULL,
    pipeline_type text NOT NULL CHECK (pipeline_type IN ('water', 'sewer', 'gas', 'district_heating', 'other')),
    install_date date,
    operator_org_id uuid REFERENCES iam.organizations(id),
    geom geometry(MultiLineString, 4326) NOT NULL,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);

CREATE INDEX pipelines_geom_gix ON asset.pipelines USING gist (geom);
CREATE INDEX pipelines_tenant_idx ON asset.pipelines (tenant_id);
```

#### `asset.pipeline_segments`

```sql
CREATE TABLE asset.pipeline_segments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES iam.tenants(id),
    pipeline_id uuid NOT NULL REFERENCES asset.pipelines(id),
    code text NOT NULL,
    material text,
    diameter_mm numeric(10, 2),
    depth_m numeric(6, 2),
    length_m numeric(12, 2),
    risk_grade text CHECK (risk_grade IN ('A', 'B', 'C', 'D', 'E')),
    install_date date,
    geom geometry(LineString, 4326) NOT NULL,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);

CREATE INDEX pipeline_segments_geom_gix ON asset.pipeline_segments USING gist (geom);
CREATE INDEX pipeline_segments_pipeline_idx ON asset.pipeline_segments (pipeline_id);
CREATE INDEX pipeline_segments_risk_idx ON asset.pipeline_segments (tenant_id, risk_grade);
```

#### `asset.sensors`

```sql
CREATE TABLE asset.sensors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES iam.tenants(id),
    segment_id uuid REFERENCES asset.pipeline_segments(id),
    sensor_code text NOT NULL,
    name text NOT NULL,
    sensor_type text NOT NULL CHECK (sensor_type IN ('pressure', 'flow', 'water_level', 'vibration', 'gas', 'temperature')),
    unit text NOT NULL,
    min_value double precision,
    max_value double precision,
    warning_min double precision,
    warning_max double precision,
    critical_min double precision,
    critical_max double precision,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance', 'retired')),
    geom geometry(Point, 4326) NOT NULL,
    installed_at timestamptz,
    last_seen_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, sensor_code)
);

CREATE INDEX sensors_geom_gix ON asset.sensors USING gist (geom);
CREATE INDEX sensors_segment_idx ON asset.sensors (segment_id);
CREATE INDEX sensors_type_status_idx ON asset.sensors (tenant_id, sensor_type, status);
```

#### `telemetry.sensor_readings`

```sql
CREATE TABLE telemetry.sensor_readings (
    id bigserial,
    tenant_id uuid NOT NULL REFERENCES iam.tenants(id),
    sensor_id uuid NOT NULL REFERENCES asset.sensors(id),
    measured_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    value double precision NOT NULL,
    unit text NOT NULL,
    quality jsonb NOT NULL DEFAULT '{}'::jsonb,
    raw_payload jsonb,
    PRIMARY KEY (id, measured_at)
);

SELECT create_hypertable('telemetry.sensor_readings', 'measured_at', if_not_exists => TRUE);

CREATE INDEX sensor_readings_sensor_time_idx
    ON telemetry.sensor_readings (sensor_id, measured_at DESC);
CREATE INDEX sensor_readings_tenant_time_idx
    ON telemetry.sensor_readings (tenant_id, measured_at DESC);
```

TimescaleDB retention 정책은 MVP에서 1년 원본 보관, 5년 집계 보관을 기본값으로 둔다.

```sql
SELECT add_retention_policy('telemetry.sensor_readings', INTERVAL '12 months');
```

#### `monitoring.anomaly_events`

```sql
CREATE TABLE monitoring.anomaly_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES iam.tenants(id),
    sensor_id uuid REFERENCES asset.sensors(id),
    segment_id uuid REFERENCES asset.pipeline_segments(id),
    detected_at timestamptz NOT NULL DEFAULT now(),
    event_start_at timestamptz NOT NULL,
    event_end_at timestamptz,
    anomaly_type text NOT NULL CHECK (anomaly_type IN ('threshold', 'trend', 'spike', 'drop', 'leak_suspected', 'sensor_fault')),
    score numeric(5, 4) NOT NULL CHECK (score >= 0 AND score <= 1),
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
    model_version text,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX anomaly_events_tenant_status_idx ON monitoring.anomaly_events (tenant_id, status, severity);
CREATE INDEX anomaly_events_time_idx ON monitoring.anomaly_events (tenant_id, detected_at DESC);
CREATE INDEX anomaly_events_segment_idx ON monitoring.anomaly_events (segment_id);
```

#### `monitoring.alerts`

```sql
CREATE TABLE monitoring.alerts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES iam.tenants(id),
    anomaly_event_id uuid REFERENCES monitoring.anomaly_events(id),
    title text NOT NULL,
    description text,
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    status text NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'assigned', 'in_progress', 'resolved', 'closed')),
    acknowledged_by uuid REFERENCES iam.users(id),
    acknowledged_at timestamptz,
    closed_by uuid REFERENCES iam.users(id),
    closed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX alerts_queue_idx ON monitoring.alerts (tenant_id, status, severity, created_at DESC);
```

### 4.4 공간 쿼리 요구사항

| 기능 | PostGIS 사용 예 |
| --- | --- |
| 지도 영역 내 배관 조회 | `ST_Intersects(geom, ST_MakeEnvelope(..., 4326))` |
| 센서 주변 반경 검색 | `ST_DWithin(geom::geography, point::geography, radius_m)` |
| 이상 이벤트 위치 표시 | 센서 point 또는 배관 segment geometry 조인 |
| 점검 대상 자동 추천 | `ST_Distance`와 배관 위험 등급, 최근 알림 가중치 조합 |
| 관로 길이 계산 | `ST_Length(geom::geography)` |

### 4.5 멀티테넌시와 Row Level Security

MVP에서는 모든 주요 테이블에 `tenant_id`를 포함한다. API 레벨에서 테넌트 필터를 강제하고, 운영 환경에서는 PostgreSQL RLS를 추가로 적용한다.

```sql
ALTER TABLE asset.sensors ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_sensors ON asset.sensors
USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

## 5. RBAC 권한 체계

### 5.1 권한 모델

권한은 `resource:action` 형식으로 정의한다.

| 리소스 | 액션 | 예시 권한 |
| --- | --- | --- |
| `dashboard` | `read` | `dashboard:read` |
| `map` | `read`, `export` | `map:read`, `map:export` |
| `pipeline` | `create`, `read`, `update`, `delete`, `import` | `pipeline:update` |
| `sensor` | `create`, `read`, `update`, `delete`, `ingest` | `sensor:ingest` |
| `telemetry` | `read`, `export` | `telemetry:read` |
| `anomaly` | `read`, `update`, `dismiss` | `anomaly:dismiss` |
| `alert` | `read`, `assign`, `ack`, `resolve`, `close` | `alert:assign` |
| `inspection` | `create`, `read`, `update`, `complete` | `inspection:complete` |
| `user` | `create`, `read`, `update`, `delete` | `user:create` |
| `role` | `create`, `read`, `update`, `delete` | `role:update` |
| `audit` | `read` | `audit:read` |
| `system` | `configure` | `system:configure` |

### 5.2 기본 역할

| 역할 코드 | 설명 | 핵심 권한 |
| --- | --- | --- |
| `SYSTEM_ADMIN` | 전체 시스템 관리자 | 모든 권한 |
| `TENANT_ADMIN` | 테넌트 관리자 | 사용자, 역할, 자산, 센서, 알림 관리 |
| `CONTROL_MANAGER` | 관제 관리자 | 대시보드 조회, 알림 배정/종료, 점검 생성 |
| `CONTROL_OPERATOR` | 관제 운영자 | 지도/센서/알림 조회, 알림 확인, 점검 요청 |
| `FIELD_INSPECTOR` | 현장 점검자 | 배정 점검 조회, 점검 기록 작성 |
| `DATA_ANALYST` | 분석가 | 시계열/이상 데이터 조회, 내보내기 |
| `AUDITOR` | 감사자 | 감사 로그 및 이력 조회 |
| `VIEWER` | 읽기 전용 사용자 | 대시보드, 지도, 배관, 센서 읽기 |

### 5.3 권한 검사 원칙

- 모든 API는 인증된 사용자만 접근 가능하다. 단, 헬스체크는 제외한다.
- JWT에는 `user_id`, `tenant_id`, `role_codes`, `permission_codes`를 포함한다.
- Backend는 라우터 또는 service layer에서 권한을 검사한다.
- 데이터 조회는 반드시 `tenant_id` 조건을 포함한다.
- 알림 배정, 종료, 권한 변경, 데이터 삭제는 감사 로그를 기록한다.
- 현장 점검자는 본인에게 배정된 점검 또는 같은 조직의 점검만 수정할 수 있다.

## 6. API 목록

### 6.1 공통 규칙

- Base URL: `/api/v1`
- 인증: `Authorization: Bearer <access_token>`
- 응답 포맷:

```json
{
  "data": {},
  "meta": {},
  "error": null
}
```

- 오류 포맷:

```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "ALERT_NOT_FOUND",
    "message": "Alert not found",
    "details": {}
  }
}
```

### 6.2 인증/IAM API

| Method | Path | 권한 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/auth/login` | public | 이메일/비밀번호 로그인 |
| `POST` | `/auth/refresh` | authenticated | 토큰 재발급 |
| `POST` | `/auth/logout` | authenticated | 로그아웃 |
| `GET` | `/auth/me` | authenticated | 내 프로필과 권한 조회 |
| `GET` | `/users` | `user:read` | 사용자 목록 조회 |
| `POST` | `/users` | `user:create` | 사용자 생성 |
| `GET` | `/users/{user_id}` | `user:read` | 사용자 상세 조회 |
| `PATCH` | `/users/{user_id}` | `user:update` | 사용자 수정 |
| `DELETE` | `/users/{user_id}` | `user:delete` | 사용자 비활성화 |
| `GET` | `/roles` | `role:read` | 역할 목록 조회 |
| `POST` | `/roles` | `role:create` | 역할 생성 |
| `PATCH` | `/roles/{role_id}` | `role:update` | 역할 권한 수정 |
| `GET` | `/permissions` | `role:read` | 권한 목록 조회 |

### 6.3 GIS/자산 API

| Method | Path | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/map/layers` | `map:read` | 사용 가능한 지도 레이어 목록 |
| `GET` | `/pipelines` | `pipeline:read` | 배관 목록, bbox 필터 지원 |
| `POST` | `/pipelines` | `pipeline:create` | 배관 생성 |
| `GET` | `/pipelines/{pipeline_id}` | `pipeline:read` | 배관 상세 조회 |
| `PATCH` | `/pipelines/{pipeline_id}` | `pipeline:update` | 배관 수정 |
| `DELETE` | `/pipelines/{pipeline_id}` | `pipeline:delete` | 배관 삭제 또는 비활성화 |
| `POST` | `/pipelines/import` | `pipeline:import` | GeoJSON/CSV 배관 일괄 업로드 |
| `GET` | `/segments` | `pipeline:read` | 배관 구간 목록, 공간 필터 지원 |
| `POST` | `/segments` | `pipeline:create` | 배관 구간 생성 |
| `GET` | `/segments/{segment_id}` | `pipeline:read` | 배관 구간 상세 조회 |
| `PATCH` | `/segments/{segment_id}` | `pipeline:update` | 배관 구간 수정 |
| `GET` | `/segments/{segment_id}/nearby-sensors` | `sensor:read` | 구간 주변 센서 조회 |

### 6.4 센서/시계열 API

| Method | Path | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/sensors` | `sensor:read` | 센서 목록, bbox/status/type 필터 지원 |
| `POST` | `/sensors` | `sensor:create` | 센서 등록 |
| `GET` | `/sensors/{sensor_id}` | `sensor:read` | 센서 상세 조회 |
| `PATCH` | `/sensors/{sensor_id}` | `sensor:update` | 센서 수정 |
| `POST` | `/sensors/{sensor_id}/readings` | `sensor:ingest` | 단건 센서 데이터 수집 |
| `POST` | `/telemetry/ingest` | `sensor:ingest` | 다건 센서 데이터 수집 |
| `GET` | `/sensors/{sensor_id}/readings` | `telemetry:read` | 센서 시계열 조회 |
| `GET` | `/telemetry/summary` | `telemetry:read` | 센서 타입별 통계 조회 |
| `GET` | `/telemetry/export` | `telemetry:export` | CSV 내보내기 |

### 6.5 AI/이상 탐지 API

| Method | Path | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/anomalies` | `anomaly:read` | 이상 이벤트 목록 조회 |
| `GET` | `/anomalies/{event_id}` | `anomaly:read` | 이상 이벤트 상세 및 근거 조회 |
| `PATCH` | `/anomalies/{event_id}/status` | `anomaly:update` | 이상 이벤트 상태 변경 |
| `POST` | `/anomalies/{event_id}/dismiss` | `anomaly:dismiss` | 오탐 처리 |
| `POST` | `/ai/inference/run` | `system:configure` | 수동 추론 실행 |
| `GET` | `/ai/models/current` | `anomaly:read` | 현재 모델 버전과 설정 조회 |

### 6.6 알림/점검 API

| Method | Path | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/alerts` | `alert:read` | 알림 큐 목록 조회 |
| `GET` | `/alerts/{alert_id}` | `alert:read` | 알림 상세 조회 |
| `POST` | `/alerts/{alert_id}/ack` | `alert:ack` | 알림 확인 처리 |
| `POST` | `/alerts/{alert_id}/assign` | `alert:assign` | 담당자 배정 |
| `POST` | `/alerts/{alert_id}/resolve` | `alert:resolve` | 해결 처리 |
| `POST` | `/alerts/{alert_id}/close` | `alert:close` | 종료 처리 |
| `GET` | `/inspection-tasks` | `inspection:read` | 점검 작업 목록 조회 |
| `POST` | `/inspection-tasks` | `inspection:create` | 점검 작업 생성 |
| `GET` | `/inspection-tasks/{task_id}` | `inspection:read` | 점검 작업 상세 조회 |
| `PATCH` | `/inspection-tasks/{task_id}` | `inspection:update` | 점검 작업 수정 |
| `POST` | `/inspection-tasks/{task_id}/records` | `inspection:complete` | 점검 기록 등록 |
| `POST` | `/attachments` | authenticated | 첨부파일 업로드 URL 발급 |

### 6.7 감사/운영 API

| Method | Path | 권한 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/audit-logs` | `audit:read` | 감사 로그 조회 |
| `GET` | `/dashboard/overview` | `dashboard:read` | 대시보드 핵심 지표 |
| `GET` | `/dashboard/risk-map` | `dashboard:read` | 위험 지도 집계 |
| `GET` | `/health` | public | API 상태 확인 |
| `GET` | `/health/dependencies` | `system:configure` | DB, Redis, MQTT 연결 상태 확인 |

## 7. Frontend 구조

### 7.1 기술 스택

| 영역 | 선택지 | MVP 권장 |
| --- | --- | --- |
| Framework | React, Next.js | Next.js App Router |
| Language | TypeScript | TypeScript |
| 지도 | MapLibre GL JS, OpenLayers | MapLibre GL JS |
| 상태 관리 | Zustand, Redux Toolkit | Zustand + TanStack Query |
| UI Kit | MUI, Ant Design, shadcn/ui | MUI 또는 shadcn/ui |
| 차트 | ECharts, Recharts | ECharts |
| 폼 | React Hook Form | React Hook Form + Zod |
| 테스트 | Vitest, Playwright | Vitest + Playwright |

### 7.2 디렉터리 구조

```text
frontend/
  src/
    app/
      layout.tsx
      page.tsx
      login/page.tsx
      dashboard/page.tsx
      map/page.tsx
      alerts/page.tsx
      alerts/[id]/page.tsx
      sensors/page.tsx
      pipelines/page.tsx
      inspections/page.tsx
      admin/users/page.tsx
      admin/roles/page.tsx
    components/
      common/
      layout/
      map/
      charts/
      forms/
      tables/
    features/
      auth/
      dashboard/
      gis/
      pipelines/
      sensors/
      telemetry/
      anomalies/
      alerts/
      inspections/
      admin/
    lib/
      api-client.ts
      auth.ts
      permissions.ts
      query-client.ts
      map-style.ts
    stores/
      auth-store.ts
      map-store.ts
      alert-store.ts
    types/
      api.ts
      domain.ts
    tests/
```

### 7.3 주요 화면

| 화면 | 기능 |
| --- | --- |
| 로그인 | 이메일/비밀번호 로그인, 토큰 저장 |
| 대시보드 | 전체 알림 수, 심각도별 이벤트, 센서 상태, 위험 구간 Top N |
| GIS 지도 | 배관/센서/이상 이벤트 레이어, bbox 조회, 객체 상세 패널 |
| 배관 관리 | 배관 목록, 상세, GeoJSON 업로드, 속성 수정 |
| 센서 관리 | 센서 목록, 위치, 상태, 최근 수신 시각, 임계치 설정 |
| 센서 상세 | 실시간/기간별 차트, 원본 데이터 테이블, 이상 이벤트 이력 |
| 알림 큐 | 상태/심각도 필터, 담당자 배정, 확인/종료 처리 |
| 점검 관리 | 점검 작업 목록, 현장 기록, 첨부파일 |
| 사용자/역할 관리 | 사용자 등록, 역할 부여, 권한 설정 |
| 감사 로그 | 권한 변경, 알림 처리, 삭제 이력 검색 |

### 7.4 Frontend 권한 처리

- 라우트 접근 전 `auth-store`와 `/auth/me` 응답의 권한을 확인한다.
- 버튼, 메뉴, 액션은 `can(permissionCode)` 헬퍼로 노출 여부를 제어한다.
- Frontend 권한 처리는 UX 목적이며, 실제 보안은 Backend 권한 검사로 보장한다.
- 지도 레이어도 권한에 따라 요청 가능한 레이어만 표시한다.

### 7.5 지도 UI 설계

- 기본 좌표계는 WGS84 `EPSG:4326`을 사용한다.
- API는 GeoJSON FeatureCollection을 반환한다.
- 대량 배관 데이터는 MVP에서는 bbox 기반 GeoJSON 조회로 처리하고, 운영 확장 시 vector tile로 전환한다.
- 레이어 구성:
  - 배관 구간 레이어: 위험 등급별 색상
  - 센서 레이어: 센서 타입별 아이콘, 상태별 테두리 색상
  - 이상 이벤트 레이어: 심각도별 마커
  - 점검 작업 레이어: 배정/진행/완료 상태 표시

## 8. Backend 구조

### 8.1 기술 스택

| 영역 | 선택지 | MVP 권장 |
| --- | --- | --- |
| API Framework | FastAPI, NestJS | FastAPI |
| Language | Python 3.12 | Python 3.12 |
| ORM/Query | SQLAlchemy, SQLModel | SQLAlchemy 2.x + Alembic |
| Validation | Pydantic | Pydantic v2 |
| Auth | JWT, OAuth2 Password Flow | JWT access/refresh token |
| Worker | Celery, RQ, Dramatiq | Celery + Redis |
| MQTT | paho-mqtt, gmqtt | paho-mqtt |
| AI | scikit-learn, PyTorch | scikit-learn baseline |
| Test | pytest | pytest |

### 8.2 디렉터리 구조

```text
backend/
  app/
    main.py
    core/
      config.py
      security.py
      database.py
      logging.py
      permissions.py
    api/
      v1/
        router.py
        auth.py
        users.py
        roles.py
        pipelines.py
        segments.py
        sensors.py
        telemetry.py
        anomalies.py
        alerts.py
        inspections.py
        audit_logs.py
        dashboard.py
    domains/
      iam/
        models.py
        schemas.py
        service.py
        repository.py
      asset/
        models.py
        schemas.py
        service.py
        repository.py
      telemetry/
        models.py
        schemas.py
        service.py
        repository.py
      monitoring/
        models.py
        schemas.py
        service.py
        repository.py
      audit/
        models.py
        service.py
    workers/
      celery_app.py
      telemetry_collector.py
      inference_worker.py
      alert_escalation_worker.py
    ai/
      features.py
      baseline_detector.py
      inference.py
      model_registry.py
    migrations/
      versions/
    tests/
```

### 8.3 Backend 계층 규칙

- `api` 계층은 request/response 변환과 권한 검사만 담당한다.
- `service` 계층은 도메인 정책, 상태 전이, 감사 로그 생성을 담당한다.
- `repository` 계층은 DB 쿼리를 담당한다.
- SQLAlchemy model은 DB 구조를 표현하고, Pydantic schema는 API 계약을 표현한다.
- 모든 쓰기 작업은 명시적 트랜잭션 안에서 수행한다.
- 상태 전이는 service method로만 수행하고, API에서 직접 status를 변경하지 않는다.

### 8.4 AI 이상 탐지 MVP 설계

MVP의 AI는 복잡한 학습 시스템보다 운영 가능한 baseline 모델을 우선한다.

| 탐지 방식 | 설명 | 적용 대상 |
| --- | --- | --- |
| 정적 임계치 | 센서별 warning/critical 범위 위반 탐지 | 전체 센서 |
| 이동 평균 편차 | 최근 값이 이동 평균 대비 일정 표준편차 이상 벗어나는지 탐지 | 압력, 유량, 수위 |
| 급격한 변화율 | 단기간 변화율이 기준을 초과하는지 탐지 | 압력, 유량 |
| 센서 무응답 | `last_seen_at`이 기준 시간을 초과하는지 탐지 | 전체 센서 |
| 누수 의심 룰 | 압력 저하와 유량 증가 조합 탐지 | 상수도, 열수송관 |

AI 결과의 `evidence` 예시는 다음과 같다.

```json
{
  "window": "30m",
  "latest_value": 2.1,
  "moving_average": 4.8,
  "z_score": -3.4,
  "threshold": {
    "critical_min": 2.5,
    "critical_max": 8.0
  },
  "related_sensor_ids": ["..."],
  "reason": "pressure_drop_detected"
}
```

## 9. Docker 구성

### 9.1 컨테이너 목록

| 서비스 | 이미지/빌드 | 포트 | 설명 |
| --- | --- | --- | --- |
| `frontend` | local build | `3000` | Next.js web console |
| `backend` | local build | `8000` | FastAPI REST API |
| `worker` | local build | 없음 | Celery worker, AI inference |
| `scheduler` | local build | 없음 | Celery beat 또는 scheduler |
| `postgres` | `postgis/postgis:16-3.4` | `5432` | PostgreSQL + PostGIS |
| `redis` | `redis:7-alpine` | `6379` | cache, queue broker |
| `mqtt` | `eclipse-mosquitto:2` | `1883` | MQTT broker |
| `minio` | `minio/minio` | `9000`, `9001` | object storage |
| `nginx` | `nginx:alpine` | `80` | reverse proxy, optional |

### 9.2 `docker-compose.yml` 초안

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: nh3
      POSTGRES_USER: nh3
      POSTGRES_PASSWORD: nh3_dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nh3 -d nh3"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  mqtt:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
    volumes:
      - ./docker/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio_dev_password
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  backend:
    build:
      context: ./backend
    environment:
      DATABASE_URL: postgresql+psycopg://nh3:nh3_dev_password@postgres:5432/nh3
      REDIS_URL: redis://redis:6379/0
      MQTT_URL: mqtt://mqtt:1883
      S3_ENDPOINT_URL: http://minio:9000
      S3_BUCKET: nh3-attachments
      JWT_SECRET_KEY: change-me-in-production
      APP_ENV: local
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      mqtt:
        condition: service_started
      minio:
        condition: service_started

  worker:
    build:
      context: ./backend
    command: celery -A app.workers.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+psycopg://nh3:nh3_dev_password@postgres:5432/nh3
      REDIS_URL: redis://redis:6379/0
      MQTT_URL: mqtt://mqtt:1883
      S3_ENDPOINT_URL: http://minio:9000
      S3_BUCKET: nh3-attachments
      JWT_SECRET_KEY: change-me-in-production
      APP_ENV: local
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  scheduler:
    build:
      context: ./backend
    command: celery -A app.workers.celery_app beat --loglevel=info
    environment:
      DATABASE_URL: postgresql+psycopg://nh3:nh3_dev_password@postgres:5432/nh3
      REDIS_URL: redis://redis:6379/0
      APP_ENV: local
    depends_on:
      redis:
        condition: service_started

  frontend:
    build:
      context: ./frontend
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000/api/v1
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_started

volumes:
  postgres_data:
  minio_data:
```

### 9.3 환경 변수

| 변수 | 설명 | 예시 |
| --- | --- | --- |
| `DATABASE_URL` | Backend DB 접속 문자열 | `postgresql+psycopg://nh3:...@postgres:5432/nh3` |
| `REDIS_URL` | Redis 접속 문자열 | `redis://redis:6379/0` |
| `MQTT_URL` | MQTT broker 주소 | `mqtt://mqtt:1883` |
| `S3_ENDPOINT_URL` | MinIO/S3 endpoint | `http://minio:9000` |
| `S3_BUCKET` | 첨부파일 버킷 | `nh3-attachments` |
| `JWT_SECRET_KEY` | JWT 서명 키 | 운영 환경에서는 secret manager 사용 |
| `ACCESS_TOKEN_TTL_MINUTES` | access token 만료 시간 | `30` |
| `REFRESH_TOKEN_TTL_DAYS` | refresh token 만료 일수 | `14` |
| `AI_INFERENCE_INTERVAL_MINUTES` | 추론 주기 | `5` |

## 10. 개발 마일스톤

| 단계 | 산출물 | 기준 |
| --- | --- | --- |
| 1단계 | Docker, DB migration, 기본 IAM | 로그인과 권한 검사가 동작한다. |
| 2단계 | 배관/센서 CRUD, 지도 조회 | bbox 기반 지도 조회가 동작한다. |
| 3단계 | 센서 수집과 시계열 조회 | MQTT 또는 REST 수집 후 차트 조회가 가능하다. |
| 4단계 | 이상 탐지 baseline, 알림 큐 | 임계치/이동평균 기반 알림이 생성된다. |
| 5단계 | 점검 워크플로우, 첨부파일 | 알림에서 점검 생성과 결과 등록이 가능하다. |
| 6단계 | 감사 로그, 운영 대시보드 | 주요 액션 이력과 운영 지표를 조회할 수 있다. |

## 11. 비기능 요구사항

| 항목 | MVP 기준 |
| --- | --- |
| 인증 | JWT access/refresh token, 비밀번호 bcrypt/argon2 해시 |
| 권한 | RBAC + tenant isolation |
| 응답 성능 | 일반 목록 API p95 500ms 이하, 지도 bbox API p95 1초 이하 |
| 데이터 보관 | 원본 센서 데이터 12개월, 집계 데이터 5년 |
| 감사 | 권한 변경, 알림 상태 변경, 삭제 작업 감사 로그 저장 |
| 관측성 | JSON log, request id, health check, worker job log |
| 백업 | PostgreSQL 일 단위 백업, MinIO 버킷 백업 |
| 보안 | 운영 환경 HTTPS, CORS allowlist, rate limiting, secret manager 사용 |

## 12. MVP 수용 기준

- 관리자는 사용자와 역할을 생성하고 권한을 부여할 수 있다.
- 운영자는 지도에서 배관, 센서, 이상 이벤트를 확인할 수 있다.
- 센서 데이터가 REST 또는 MQTT로 수집되고 시계열 차트로 조회된다.
- 임계치 또는 이동 평균 기반 이상 이벤트가 생성된다.
- 이상 이벤트로부터 알림이 생성되고 담당자 배정, 확인, 해결, 종료 처리가 가능하다.
- 알림 기반 점검 작업을 생성하고 점검 기록과 첨부파일을 등록할 수 있다.
- 주요 업무 변경 사항이 감사 로그에 저장된다.
- Docker Compose로 로컬 개발 환경을 기동할 수 있다.
