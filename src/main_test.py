from __future__ import annotations

import pytest

from src.main import build_parser


def test_parser_chat() -> None:
    parser = build_parser()
    args = parser.parse_args(["chat"])
    assert args.command == "chat"


def test_parser_ask() -> None:
    parser = build_parser()
    args = parser.parse_args(["ask", "What time is it?"])
    assert args.command == "ask"
    assert args.query == "What time is it?"


def test_parser_auth_google() -> None:
    parser = build_parser()
    args = parser.parse_args(["auth", "google"])
    assert args.command == "auth"
    assert args.service == "google"


def test_parser_config_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--config", "custom.yaml", "chat"])
    assert args.config == "custom.yaml"
    assert args.command == "chat"


def test_parser_default_config() -> None:
    parser = build_parser()
    args = parser.parse_args(["chat"])
    assert args.config == "config.yaml"


def test_parser_no_command() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None
