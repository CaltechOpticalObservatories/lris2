"""Shared MJPEG capture that runs only while someone is watching."""

from __future__ import annotations

import io
import subprocess
import threading
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Final, Protocol, cast

_SOI: Final = b"\xff\xd8"
_EOI: Final = b"\xff\xd9"
_READ_CHUNK: Final = 65536
_FRAME_TIMEOUT_S: Final = 5.0


class FrameSource(Protocol):
    """A process-like source of concatenated JPEG frames."""

    def read(self, size: int) -> bytes:
        """Return up to ``size`` bytes, or ``b""`` at end of stream."""

    def close(self) -> None:
        """Stop producing frames."""


@dataclass(frozen=True)
class StreamFormat:
    """What viewers receive; the camera always captures 1280x720 MJPEG at 30 fps."""

    width: int = 960
    height: int = 540
    fps: int = 15
    quality: int = 60


def gstreamer_argv(device: str, stream: StreamFormat) -> list[str]:
    """Return a pipeline that re-encodes the camera's MJPEG to a lighter stream."""
    return [
        "gst-launch-1.0", "-q", "v4l2src", f"device={device}",
        "!", "image/jpeg,width=1280,height=720,framerate=30/1",
        "!", "jpegdec", "!", "videorate", "!", f"video/x-raw,framerate={stream.fps}/1",
        "!", "videoscale", "!", f"video/x-raw,width={stream.width},height={stream.height}",
        "!", "jpegenc", f"quality={stream.quality}", "!", "fdsink",
    ]


class CommandSource:
    """JPEG frames from a capture command's stdout."""

    def __init__(self, argv: Sequence[str]) -> None:
        self._process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self._stdout = cast(io.BufferedReader, self._process.stdout)

    def read(self, size: int) -> bytes:
        return self._stdout.read1(size)

    def close(self) -> None:
        self._process.terminate()
        try:
            self._process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._process.kill()


class SourceFactory(Protocol):
    """Callable that starts a new capture."""

    def __call__(self) -> FrameSource:
        """Start capturing."""


class SharedCamera:
    """Fan one capture out to any number of viewers."""

    def __init__(self, start_source: SourceFactory) -> None:
        self._start_source = start_source
        self._condition = threading.Condition()
        self._frame: bytes | None = None
        self._frame_number = 0
        self._viewers = 0
        self._source: FrameSource | None = None

    @property
    def viewers(self) -> int:
        """Return how many streams are open."""
        with self._condition:
            return self._viewers

    @property
    def running(self) -> bool:
        """Return whether a capture is active."""
        with self._condition:
            return self._source is not None

    def frames(self) -> Iterator[bytes]:
        """Yield JPEG frames for one viewer until the caller stops iterating."""
        self._attach()
        try:
            seen = 0
            while (frame := self._next_frame(seen)) is not None:
                seen = frame[0]
                yield frame[1]
        finally:
            self._detach()

    def _next_frame(self, seen: int) -> tuple[int, bytes] | None:
        """Wait for a frame newer than ``seen``; None once capture has ended."""
        with self._condition:
            fresh = self._condition.wait_for(
                lambda: (self._frame is not None and self._frame_number != seen)
                or self._source is None,
                timeout=_FRAME_TIMEOUT_S,
            )
            if not fresh or self._frame is None:
                return None
            return self._frame_number, self._frame

    def _attach(self) -> None:
        with self._condition:
            self._viewers += 1
            if self._source is not None:
                return
            self._source = self._start_source()
            source = self._source
        threading.Thread(target=self._pump, args=(source,), name="camera", daemon=True).start()

    def _detach(self) -> None:
        with self._condition:
            self._viewers -= 1
            if self._viewers > 0 or self._source is None:
                return
            source, self._source = self._source, None
            self._frame = None
            self._condition.notify_all()
        source.close()

    def _pump(self, source: FrameSource) -> None:
        buffer = b""
        while chunk := source.read(_READ_CHUNK):
            buffer += chunk
            while (start := buffer.find(_SOI)) >= 0 and (end := buffer.find(_EOI, start + 2)) >= 0:
                self._publish(buffer[start : end + 2])
                buffer = buffer[end + 2 :]
        with self._condition:
            if self._source is source:
                self._source = None
            self._condition.notify_all()

    def _publish(self, frame: bytes) -> None:
        with self._condition:
            self._frame = frame
            self._frame_number += 1
            self._condition.notify_all()
