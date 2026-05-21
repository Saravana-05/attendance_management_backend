-- =============================================================
--  Attendance System – Database Schema

-- =============================================================

-- 1. employees
CREATE TABLE IF NOT EXISTS employees (
    id        SERIAL       PRIMARY KEY,
    name      TEXT         NOT NULL,
    photo     TEXT         NOT NULL,
    encoding  TEXT         NOT NULL
);

-- 2. attendance
CREATE TABLE IF NOT EXISTS attendance (
    id             SERIAL       PRIMARY KEY,
    employee_id    INTEGER      NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    employee_name  TEXT         NOT NULL,
    date           DATE         NOT NULL,
    login_time     TEXT,
    logout_time    TEXT,
    login_photo    TEXT,
    logout_photo   TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_employee_date
    ON attendance (employee_id, date);

CREATE INDEX IF NOT EXISTS idx_emp_date
    ON attendance (employee_id, date);

CREATE INDEX IF NOT EXISTS idx_date
    ON attendance (date);

-- Safe migration: add photo columns if absent on existing installs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='attendance' AND column_name='login_photo'
    ) THEN
        ALTER TABLE attendance ADD COLUMN login_photo TEXT;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='attendance' AND column_name='logout_photo'
    ) THEN
        ALTER TABLE attendance ADD COLUMN logout_photo TEXT;
    END IF;
END
$$;

-- 3. attendance_breaks
CREATE TABLE IF NOT EXISTS attendance_breaks (
    id             SERIAL       PRIMARY KEY,
    attendance_id  INTEGER      NOT NULL REFERENCES attendance(id) ON DELETE CASCADE,
    break_start    TEXT         NOT NULL,
    break_end      TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_breaks_attendance
    ON attendance_breaks (attendance_id);

CREATE INDEX IF NOT EXISTS idx_breaks_active
    ON attendance_breaks (attendance_id) WHERE break_end IS NULL;

-- 4. leave_requests
CREATE TABLE IF NOT EXISTS leave_requests (
    id             SERIAL       PRIMARY KEY,
    employee_id    INTEGER      NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    employee_name  TEXT         NOT NULL,
    leave_type     TEXT         NOT NULL,
    from_date      DATE         NOT NULL,
    to_date        DATE         NOT NULL,
    reason         TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_leave_dates CHECK (to_date >= from_date)
);

CREATE INDEX IF NOT EXISTS idx_leave_emp
    ON leave_requests (employee_id);