from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.assets import Pipeline, Sensor
from app.models.iam import Organization, Role, User
from app.models.monitoring import AIAnalysis, Notification, RiskEvent
from app.models.telemetry import SensorData

DEFAULT_ROLES = [
    ("SuperAdmin", "SuperAdmin", "System-wide administrator"),
    ("Admin", "Admin", "Organization administrator"),
    ("Manager", "Manager", "Operations manager"),
    ("Operator", "Operator", "Control room operator"),
    ("FieldWorker", "FieldWorker", "Field worker"),
]

SEED_ORGANIZATIONS = [
    ("NH3", "NH3 Operations"),
    ("NH3-SEOUL", "NH3 Seoul Field Office"),
    ("NH3-BUSAN", "NH3 Busan Field Office"),
]

SEED_USERS = [
    ("admin@nh3.local", "NH3 Super Admin", "SuperAdmin", "NH3"),
    ("admin.seoul@nh3.local", "Seoul Admin", "Admin", "NH3-SEOUL"),
    ("admin.busan@nh3.local", "Busan Admin", "Admin", "NH3-BUSAN"),
    ("manager.01@nh3.local", "Operations Manager 01", "Manager", "NH3"),
    ("manager.02@nh3.local", "Operations Manager 02", "Manager", "NH3-SEOUL"),
    ("operator.01@nh3.local", "Control Operator 01", "Operator", "NH3"),
    ("operator.02@nh3.local", "Control Operator 02", "Operator", "NH3-BUSAN"),
    ("field.01@nh3.local", "Field Worker 01", "FieldWorker", "NH3-SEOUL"),
    ("field.02@nh3.local", "Field Worker 02", "FieldWorker", "NH3-BUSAN"),
    ("field.03@nh3.local", "Field Worker 03", "FieldWorker", "NH3"),
]

PIPELINE_TARGET_COUNT = 50
SENSOR_TARGET_COUNT = 300
SENSOR_DATA_TARGET_COUNT = 5_000
AI_ANALYSIS_TARGET_COUNT = 100
RISK_EVENT_TARGET_COUNT = 20
NOTIFICATION_TARGET_COUNT = 50

SENSOR_PROFILES = [
    ("Pressure", "bar", 1.5, 12.0),
    ("Flow", "m3/h", 10.0, 450.0),
    ("Vibration", "mm/s", 0.0, 15.0),
    ("Leakage", "ppm", 0.0, 100.0),
    ("Temperature", "celsius", -10.0, 90.0),
]

SEVERITY_BY_SCORE = [
    (90, "Critical"),
    (75, "High"),
    (55, "Medium"),
    (30, "Low"),
    (0, "Normal"),
]


def _count(db: Session, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _risk_severity(score: float) -> str:
    for threshold, severity in SEVERITY_BY_SCORE:
        if score >= threshold:
            return severity
    return "Normal"


def _point(lon: float, lat: float) -> WKTElement:
    return WKTElement(f"POINT({lon:.6f} {lat:.6f})", srid=4326)


def _line(start_lon: float, start_lat: float, end_lon: float, end_lat: float) -> WKTElement:
    return WKTElement(
        f"LINESTRING({start_lon:.6f} {start_lat:.6f}, {end_lon:.6f} {end_lat:.6f})",
        srid=4326,
    )


def seed_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for code, name, description in DEFAULT_ROLES:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(code=code, name=name, description=description, is_system=True)
            db.add(role)
            db.flush()
        roles[code] = role
    return roles


def seed_organizations(db: Session) -> dict[str, Organization]:
    organizations: dict[str, Organization] = {}
    for code, name in SEED_ORGANIZATIONS:
        organization = db.scalar(select(Organization).where(Organization.code == code))
        if organization is None:
            organization = Organization(name=name, code=code)
            db.add(organization)
            db.flush()
        organizations[code] = organization
    return organizations


def seed_users(
    db: Session,
    roles: dict[str, Role],
    organizations: dict[str, Organization],
) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, name, role_code, organization_code in SEED_USERS:
        user = db.scalar(select(User).where(User.email == email))
        organization = organizations[organization_code]
        if user is None:
            password = (
                settings.first_superadmin_password
                if email == settings.first_superadmin_email
                else "ChangeMe123!"
            )
            user = User(
                organization_id=organization.id,
                email=email,
                password_hash=hash_password(password),
                name=name,
                status="active",
            )
            db.add(user)
            db.flush()
        elif user.organization_id is None:
            user.organization_id = organization.id

        role = roles[role_code]
        if role not in user.roles:
            user.roles.append(role)
        users[email] = user

    superadmin = users.get(settings.first_superadmin_email)
    if superadmin is not None and roles["SuperAdmin"] not in superadmin.roles:
        superadmin.roles.append(roles["SuperAdmin"])
    return users


def seed_pipelines(
    db: Session,
    organizations: dict[str, Organization],
    creator: User,
) -> list[Pipeline]:
    existing_count = _count(db, Pipeline)
    if existing_count < PIPELINE_TARGET_COUNT:
        orgs = list(organizations.values())
        for idx in range(existing_count + 1, PIPELINE_TARGET_COUNT + 1):
            code = f"PL-{idx:04d}"
            if db.scalar(select(Pipeline).where(Pipeline.code == code)) is not None:
                continue
            base_lon = 126.82 + (idx % 10) * 0.018
            base_lat = 37.44 + (idx // 10) * 0.018
            pipeline = Pipeline(
                organization_id=orgs[idx % len(orgs)].id,
                code=code,
                name=f"MVP Test Pipeline {idx:02d}",
                pipeline_type="Gas",
                material=["DuctileIron", "Steel", "HDPE", "CastIron"][idx % 4],
                diameter_mm=150 + (idx % 8) * 50,
                depth_m=1.2 + (idx % 6) * 0.25,
                length_m=950 + idx * 37,
                risk_grade=["A", "B", "C", "D"][idx % 4],
                installed_at=date(2010 + (idx % 12), ((idx % 12) + 1), min((idx % 28) + 1, 28)),
                geom=_line(base_lon, base_lat, base_lon + 0.012, base_lat + 0.007),
                properties={
                    "seed": True,
                    "district": ["Gangnam", "Seocho", "Mapo", "Busan"][idx % 4],
                },
                created_by=creator.id,
            )
            db.add(pipeline)
        db.flush()

    return list(db.scalars(select(Pipeline).order_by(Pipeline.code).limit(PIPELINE_TARGET_COUNT)))


def seed_sensors(db: Session, pipelines: list[Pipeline], creator: User) -> list[Sensor]:
    existing_count = _count(db, Sensor)
    if existing_count < SENSOR_TARGET_COUNT:
        for idx in range(existing_count + 1, SENSOR_TARGET_COUNT + 1):
            code = f"SN-{idx:05d}"
            if db.scalar(select(Sensor).where(Sensor.sensor_code == code)) is not None:
                continue
            pipeline = pipelines[(idx - 1) % len(pipelines)]
            sensor_type, unit, min_value, max_value = SENSOR_PROFILES[
                (idx - 1) % len(SENSOR_PROFILES)
            ]
            status = ["Online", "Online", "Online", "Warning", "Critical", "Offline"][idx % 6]
            lon = 126.82 + (idx % 30) * 0.006
            lat = 37.44 + (idx // 30) * 0.006
            sensor = Sensor(
                pipeline_id=pipeline.id,
                sensor_code=code,
                name=f"{sensor_type} Sensor {idx:03d}",
                sensor_type=sensor_type,
                unit=unit,
                status=status,
                min_value=min_value,
                max_value=max_value,
                last_seen_at=datetime.now(UTC) - timedelta(minutes=idx % 180),
                geom=_point(lon, lat),
                metadata_json={
                    "seed": True,
                    "sampling_interval_sec": 60,
                    "firmware": f"1.{idx % 7}.0",
                },
                created_by=creator.id,
            )
            db.add(sensor)
        db.flush()

    return list(db.scalars(select(Sensor).order_by(Sensor.sensor_code).limit(SENSOR_TARGET_COUNT)))


def _sensor_value(sensor: Sensor, sequence: int) -> float:
    sensor_type = sensor.sensor_type
    if sensor_type == "Pressure":
        return round(7.0 - (sequence % 9) * 0.18, 4)
    if sensor_type == "Flow":
        return round(180.0 + (sequence % 40) * 2.3, 4)
    if sensor_type == "Vibration":
        return round(2.2 + (sequence % 18) * 0.31, 4)
    if sensor_type == "Leakage":
        return round((sequence % 16) * 2.7, 4)
    return round(22.0 + (sequence % 14) * 0.65, 4)


def seed_sensor_data(db: Session, sensors: list[Sensor], creator: User) -> None:
    existing_count = _count(db, SensorData)
    if existing_count >= SENSOR_DATA_TARGET_COUNT:
        return

    now = datetime.now(UTC)
    batch: list[SensorData] = []
    for idx in range(existing_count + 1, SENSOR_DATA_TARGET_COUNT + 1):
        sensor = sensors[(idx - 1) % len(sensors)]
        measured_at = now - timedelta(minutes=SENSOR_DATA_TARGET_COUNT - idx)
        batch.append(
            SensorData(
                sensor_id=sensor.id,
                measured_at=measured_at,
                received_at=measured_at + timedelta(seconds=2 + (idx % 8)),
                value=_sensor_value(sensor, idx),
                unit=sensor.unit,
                quality={"seed": True, "score": 0.92 if idx % 41 else 0.78},
                raw_payload={
                    "sequence": idx,
                    "sensor_code": sensor.sensor_code,
                    "source": "mvp-seed",
                },
                created_by=creator.id,
            )
        )
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch.clear()
    if batch:
        db.add_all(batch)
        db.flush()


def seed_ai_analyses(db: Session, sensors: list[Sensor], creator: User) -> list[AIAnalysis]:
    existing_count = _count(db, AIAnalysis)
    if existing_count < AI_ANALYSIS_TARGET_COUNT:
        now = datetime.now(UTC)
        for idx in range(existing_count + 1, AI_ANALYSIS_TARGET_COUNT + 1):
            sensor = sensors[(idx * 3 - 1) % len(sensors)]
            score = float(25 + (idx * 7) % 75)
            analysis = AIAnalysis(
                pipeline_id=sensor.pipeline_id,
                sensor_id=sensor.id,
                model_name="NH3 Sensor Fusion MVP",
                model_version="0.1.0-seed",
                analysis_type="sensor_fusion_risk_detection",
                risk_score=score,
                severity=_risk_severity(score),
                started_at=now - timedelta(minutes=idx * 6),
                ended_at=now - timedelta(minutes=idx * 6 - 1),
                evidence={
                    "seed": True,
                    "features": {
                        "pressure_drop": round((idx % 10) * 0.08, 3),
                        "vibration_delta": round((idx % 7) * 0.21, 3),
                        "leakage_signal": idx % 4 == 0,
                    },
                },
                created_by=creator.id,
            )
            db.add(analysis)
        db.flush()

    return list(
        db.scalars(
            select(AIAnalysis)
            .order_by(AIAnalysis.started_at.desc())
            .limit(AI_ANALYSIS_TARGET_COUNT)
        )
    )


def seed_risk_events(
    db: Session,
    analyses: list[AIAnalysis],
    users: dict[str, User],
    creator: User,
) -> list[RiskEvent]:
    existing_count = _count(db, RiskEvent)
    assignees = [
        user
        for email, user in users.items()
        if email.startswith("field.") or email.startswith("operator.")
    ]
    if existing_count < RISK_EVENT_TARGET_COUNT:
        now = datetime.now(UTC)
        for idx in range(existing_count + 1, RISK_EVENT_TARGET_COUNT + 1):
            event_code = f"RE-SEED-{idx:04d}"
            if db.scalar(select(RiskEvent).where(RiskEvent.event_code == event_code)) is not None:
                continue
            analysis = analyses[(idx - 1) % len(analyses)]
            score = float(55 + (idx * 9) % 45)
            status = ["Open", "Investigating", "InProgress", "Resolved", "Closed"][idx % 5]
            detected_at = now - timedelta(hours=idx * 2)
            resolved_at = (
                detected_at + timedelta(hours=6)
                if status in {"Resolved", "Closed"}
                else None
            )
            risk_event = RiskEvent(
                pipeline_id=analysis.pipeline_id,
                sensor_id=analysis.sensor_id,
                assignee_id=assignees[idx % len(assignees)].id if assignees else None,
                ai_analysis_id=analysis.id,
                event_code=event_code,
                title=f"Seed Risk Event {idx:02d} - {_risk_severity(score)} pipeline risk",
                description=(
                    "MVP seed event generated from pressure, vibration and leakage indicators."
                ),
                severity=_risk_severity(score),
                risk_score=score,
                status=status,
                location=_point(126.85 + (idx % 8) * 0.012, 37.46 + (idx % 6) * 0.01),
                detected_at=detected_at,
                resolved_at=resolved_at,
                evidence={
                    "seed": True,
                    "ai_analysis_id": str(analysis.id),
                    "scenario": "sensor-fusion",
                },
                created_by=creator.id,
            )
            db.add(risk_event)
        db.flush()

    return list(
        db.scalars(
            select(RiskEvent).order_by(RiskEvent.detected_at.desc()).limit(RISK_EVENT_TARGET_COUNT)
        )
    )


def seed_notifications(
    db: Session,
    risk_events: list[RiskEvent],
    users: dict[str, User],
    creator: User,
) -> None:
    existing_count = _count(db, Notification)
    if existing_count >= NOTIFICATION_TARGET_COUNT:
        return

    recipients = list(users.values())
    now = datetime.now(UTC)
    for idx in range(existing_count + 1, NOTIFICATION_TARGET_COUNT + 1):
        risk_event = risk_events[(idx - 1) % len(risk_events)]
        recipient = recipients[(idx - 1) % len(recipients)]
        channel = ["Dashboard", "Email", "SMS"][idx % 3]
        status = ["Pending", "Sent", "Read"][idx % 3]
        sent_at = now - timedelta(minutes=idx * 3) if status in {"Sent", "Read"} else None
        notification = Notification(
            risk_event_id=risk_event.id,
            recipient_id=recipient.id,
            channel=channel,
            title=f"[{risk_event.severity}] {risk_event.event_code}",
            message=f"{risk_event.title} requires attention from {recipient.name}.",
            status=status,
            sent_at=sent_at,
            read_at=sent_at + timedelta(minutes=7) if status == "Read" and sent_at else None,
            payload={"seed": True, "risk_event_code": risk_event.event_code, "channel": channel},
            created_by=creator.id,
        )
        db.add(notification)
    db.flush()


def seed_initial_data() -> None:
    with SessionLocal() as db:
        roles = seed_roles(db)
        organizations = seed_organizations(db)
        users = seed_users(db, roles, organizations)
        db.flush()

        creator = users.get(settings.first_superadmin_email) or users["admin@nh3.local"]
        pipelines = seed_pipelines(db, organizations, creator)
        sensors = seed_sensors(db, pipelines, creator)
        seed_sensor_data(db, sensors, creator)
        analyses = seed_ai_analyses(db, sensors, creator)
        risk_events = seed_risk_events(db, analyses, users, creator)
        seed_notifications(db, risk_events, users, creator)

        db.commit()


if __name__ == "__main__":
    seed_initial_data()
