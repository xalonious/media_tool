from __future__ import annotations

from dataclasses import dataclass
import glob
import os
from pathlib import Path
import sys
from typing import Callable, Iterable

from .errors import ToolError


@dataclass(frozen=True)
class InputFile:
    path: str
    relative_path: str
    explicit: bool


@dataclass(frozen=True)
class BatchSelection:
    files: list[InputFile]
    batch_mode: bool


@dataclass(frozen=True)
class PlannedFile:
    input: InputFile
    output_path: str


@dataclass(frozen=True)
class SkippedFile:
    path: str
    reason: str


def _directory_files(directory: str, recursive: bool) -> Iterable[InputFile]:
    root = Path(directory)
    iterator = root.rglob("*") if recursive else root.iterdir()
    for entry in sorted(iterator, key=lambda value: str(value).lower()):
        if entry.is_file():
            yield InputFile(
                path=os.path.normpath(str(entry)),
                relative_path=os.path.normpath(str(entry.relative_to(root))),
                explicit=False,
            )


def discover_inputs(specifications: list[str], recursive: bool) -> BatchSelection:
    if not specifications:
        raise ToolError("Provide at least one input file, glob, or directory.")

    files: list[InputFile] = []
    errors: list[str] = []
    batch_mode = len(specifications) > 1

    for specification in specifications:
        if glob.has_magic(specification):
            batch_mode = True
            matches = sorted(glob.glob(specification, recursive=recursive))
            if not matches:
                errors.append(f"The pattern '{specification}' matched no files.")
                continue
            for match in matches:
                if os.path.isdir(match):
                    files.extend(_directory_files(match, recursive))
                elif os.path.isfile(match):
                    files.append(
                        InputFile(
                            path=os.path.normpath(match),
                            relative_path=os.path.basename(os.path.normpath(match)),
                            explicit=False,
                        )
                    )
            continue

        if os.path.isdir(specification):
            batch_mode = True
            files.extend(_directory_files(specification, recursive))
        elif os.path.isfile(specification):
            files.append(
                InputFile(
                    path=os.path.normpath(specification),
                    relative_path=os.path.basename(os.path.normpath(specification)),
                    explicit=True,
                )
            )
        else:
            errors.append(f"The input '{specification}' does not exist.")

    if errors:
        raise ToolError("\n".join(errors))

    unique_files: list[InputFile] = []
    seen: set[str] = set()
    for input_file in files:
        identity = os.path.normcase(os.path.abspath(input_file.path))
        if identity not in seen:
            seen.add(identity)
            unique_files.append(input_file)

    if not unique_files:
        raise ToolError("No files were found in the supplied inputs.")
    if len(unique_files) > 1:
        batch_mode = True
    return BatchSelection(unique_files, batch_mode)


def output_in_directory(
    input_file: InputFile,
    output_directory: str,
    default_output: Callable[[str], str],
) -> str:
    relative_output = default_output(input_file.relative_path)
    return os.path.normpath(os.path.join(output_directory, relative_output))


def validate_output_collisions(planned: list[PlannedFile]) -> None:
    sources = {
        os.path.normcase(os.path.abspath(item.input.path)): item.input.path
        for item in planned
    }
    outputs: dict[str, str] = {}
    for item in planned:
        identity = os.path.normcase(os.path.abspath(item.output_path))
        source_at_output = sources.get(identity)
        if source_at_output is not None:
            raise ToolError(
                f"The output '{item.output_path}' would overwrite selected input "
                f"'{source_at_output}'. Choose a different output location."
            )
        previous = outputs.get(identity)
        if previous is not None:
            raise ToolError(
                f"Both '{previous}' and '{item.input.path}' would write to "
                f"'{item.output_path}'. Choose a different --output-dir."
            )
        outputs[identity] = item.input.path


def raise_preflight_errors(errors: list[str]) -> None:
    if errors:
        details = "\n".join(f"  {error}" for error in errors)
        raise ToolError(f"The batch cannot be processed:\n{details}")


def run_planned_batch(
    planned: list[PlannedFile],
    skipped: list[SkippedFile],
    processor: Callable[[str, str], None],
    batch_mode: bool,
    strict: bool,
) -> int:
    if strict and skipped:
        reasons = [f"{item.path} — {item.reason}" for item in skipped]
        raise_preflight_errors(reasons)

    if not batch_mode and len(planned) == 1 and not skipped:
        item = planned[0]
        output_parent = os.path.dirname(os.path.abspath(item.output_path))
        try:
            os.makedirs(output_parent, exist_ok=True)
        except OSError as exc:
            raise ToolError(f"Could not create output directory: {exc}") from exc
        processor(item.input.path, item.output_path)
        return 0

    for item in skipped:
        print(f"Skipping '{item.path}': {item.reason}", file=sys.stderr)

    succeeded = 0
    failures: list[tuple[str, str]] = []
    total = len(planned)
    for index, item in enumerate(planned, start=1):
        print(f"\n[{index}/{total}] {item.input.path}")
        output_parent = os.path.dirname(os.path.abspath(item.output_path))
        try:
            os.makedirs(output_parent, exist_ok=True)
            processor(item.input.path, item.output_path)
            succeeded += 1
        except (OSError, ToolError) as exc:
            failures.append((item.input.path, str(exc)))
            print(f"Failed '{item.input.path}': {exc}", file=sys.stderr)

    print("\nBatch summary")
    print(f"  Succeeded: {succeeded}")
    print(f"  Skipped:   {len(skipped)}")
    print(f"  Failed:    {len(failures)}")
    if failures:
        print("\nFailures:", file=sys.stderr)
        for path, reason in failures:
            print(f"  {path} — {reason}", file=sys.stderr)

    return 1 if failures or succeeded == 0 else 0
