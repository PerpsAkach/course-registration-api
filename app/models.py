from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("credits > 0", name="ck_course_credits_positive"),
        CheckConstraint("capacity > 0", name="ck_course_capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    sections: Mapped[list["Section"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    prerequisites: Mapped[list["Prerequisite"]] = relationship(
        foreign_keys="Prerequisite.course_id",
        back_populates="course",
        cascade="all, delete-orphan",
    )


class AcademicTerm(Base):
    __tablename__ = "academic_terms"
    __table_args__ = (
        UniqueConstraint("name", "year", name="uq_term_name_year"),
        CheckConstraint("year >= 2000", name="ck_term_year_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    registration_opens_on: Mapped[date] = mapped_column(Date, nullable=False)
    registration_closes_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    sections: Mapped[list["Section"]] = relationship(back_populates="term", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("course_id", "term_id", "section_number", name="uq_section_course_term_number"),
        CheckConstraint("capacity > 0", name="ck_section_capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True)
    section_number: Mapped[str] = mapped_column(String(16), nullable=False)
    instructor: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    meeting_days: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    starts_at: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    ends_at: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    course: Mapped[Course] = relationship(back_populates="sections")
    term: Mapped[AcademicTerm] = relationship(back_populates="sections")


class Prerequisite(Base):
    __tablename__ = "prerequisites"
    __table_args__ = (
        UniqueConstraint("course_id", "required_course_id", name="uq_course_prerequisite"),
        CheckConstraint("course_id <> required_course_id", name="ck_prerequisite_not_self"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    required_course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    course: Mapped[Course] = relationship(foreign_keys=[course_id], back_populates="prerequisites")
    required_course: Mapped[Course] = relationship(foreign_keys=[required_course_id])


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
        CheckConstraint("status IN ('active', 'dropped')", name="ck_enrollment_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    dropped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped[Student] = relationship(back_populates="enrollments")
    course: Mapped[Course] = relationship(back_populates="enrollments")
