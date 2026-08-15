"""Exam-agnostic engine pieces shared by every exam.

Nothing in here may import from an exam package. The dependency direction is
strictly one-way: exams depend on core, never the reverse. That constraint is
what keeps a new exam from having to modify shared code.
"""
