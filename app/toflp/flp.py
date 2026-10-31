"""FLP writer: put separated stems onto the playlist of a real FL project.

Strategy (deliberately conservative): we never restructure the template.
We reuse sampler channels that the template already contains (renaming
them and pointing them at our stems) and we *append* cloned playlist
items, so every byte sequence we emit is a sequence FL Studio already
produced somewhere in the file.
"""
from __future__ import annotations

import copy
import os
import sys
from dataclasses import dataclass

def _bootstrap_pyflp(libs_dir: str | None = None) -> None:
    if libs_dir and libs_dir not in sys.path:
        sys.path.insert(0, libs_dir)
    from pyflp._events import EventEnum

    if EventEnum.__members__:
        return
    dummy = int.__new__(EventEnum, -999)
    dummy._value_ = -999
    dummy.type = None
    EventEnum._member_names_.append("_DUMMY")
    EventEnum._member_map_["_DUMMY"] = dummy
    EventEnum._value2member_map_[-999] = dummy

    def _missing_(cls, value):
        if not isinstance(value, int):
            return None
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.type = None
        return obj

    EventEnum._missing_ = classmethod(_missing_)


_bootstrap_pyflp()

import pyflp  # noqa: E402
from pyflp._events import IndexedEvent, EventTree  # noqa: E402
from pyflp.arrangement import PlaylistEvent  # noqa: E402
from pyflp.channel import ChannelID  # noqa: E402
from pyflp.pattern import PatternID  # noqa: E402
from pyflp.project import ProjectID  # noqa: E402


@dataclass
class Stem:
    name: str
    path: str


@dataclass
class NoteEvent:
    pitch: int
    start_beats: float
    length_beats: float
    velocity: int = 90


def _has_sample_path(channel) -> bool:
    return any(int(e.id) == int(ChannelID.SamplePath) for e in channel.events)


def _channel_starts(events: list) -> list[int]:
    return [i for i, e in enumerate(events) if int(e.id) == int(ChannelID.New)]


def _block_end(events: list, starts: list[int], pos: int) -> int:
    """End index (exclusive) of the channel block that begins at ``starts[pos]``."""
    if pos + 1 < len(starts):
        return starts[pos + 1]
    start = starts[pos]
    for i in range(start + 1, len(events)):
        if int(events[i].id) in (int(PatternID.New), int(ChannelID.New)):
            return i
    return len(events)


def ensure_sample_paths(events: list, positions: list[int]) -> tuple[list, int]:
    """Insert a SamplePath event into the given channel blocks.

    FL only stores a sampler's file in a ``ChannelID.SamplePath`` event; a
    channel created by hand from a template may not have one, and the
    property is not writable without it.
    """
    from pyflp._events import UnicodeEvent

    starts = _channel_starts(events)
    if max(positions, default=-1) >= len(starts):
        raise RuntimeError("模板通道数量与预期不符")
    out = list(events)
    inserted = 0
    shift = 0
    for pos in sorted(positions, reverse=True):
        begin = starts[pos]
        end = _block_end(out, starts, pos)
        block = out[begin:end]
        if any(int(e.id) == int(ChannelID.SamplePath) for e in block):
            continue
        ev = UnicodeEvent(ChannelID.SamplePath, " ".encode("utf-16-le") + b"\x00\x00")
        out.insert(end, ev)
        inserted += 1
    return out, inserted


def _playlist_event(project):
    for e in project.events:
        if isinstance(e, PlaylistEvent):
            return e
    return None


def _template_item(ev) -> dict | None:
    for item in ev.value:
        if item is not None and "pattern_base" in item:
            return copy.deepcopy(dict(item))
    return None


def build_project(template: str, out: str, stems: list[Stem], bpm: float,
                  length_beats: float, title: str = "",
                  notes: list[NoteEvent] | None = None,
                  pattern_name: str = "MIDI",
                  drum_notes: list[NoteEvent] | None = None,
                  drum_pattern_name: str = "Drums") -> dict:
    project = pyflp.parse(template)
    from pyflp.channel import Sampler

    all_channels = list(project.channels)
    sampler_positions = [i for i, c in enumerate(all_channels) if isinstance(c, Sampler)]
    if len(sampler_positions) < len(stems):
        # fall back to whatever channels exist; sample paths may be ignored
        sampler_positions = list(range(min(len(all_channels), len(stems))))
    chosen_positions = sampler_positions[:len(stems)]

    events, inserted = ensure_sample_paths(list(project.events), chosen_positions)
    if inserted:
        project = pyflp.Project(
            EventTree(init=(IndexedEvent(i, e) for i, e in enumerate(events))),
            channel_count=len(project.channels),
            format=project.format,
            ppq=project.ppq,
        )

    # --- tempo / title ---
    try:
        project.tempo = float(bpm)
    except Exception:
        for e in project.events:
            if int(e.id) == int(ProjectID.Tempo):
                e.value = int(round(bpm * 1000))
    if title:
        for e in project.events:
            if int(e.id) == int(ProjectID.Title):
                e.value = title
                break

    # --- channels ---
    channels = [list(project.channels)[i] for i in chosen_positions if i < len(list(project.channels))]
    if len(channels) < len(stems):
        raise RuntimeError(f"模板通道不足：需要 {len(stems)} 个，只有 {len(channels)} 个")
    for ch, stem in zip(channels, stems):
        try:
            ch.name = stem.name
        except Exception:
            pass
        ch.sample_path = os.path.abspath(stem.path).replace("\\", "/")

    # --- playlist items ---
    ev = _playlist_event(project)
    if ev is None:
        raise RuntimeError("template has no playlist; add one audio clip to it")
    proto = _template_item(ev)
    if proto is None:
        raise RuntimeError("template playlist is empty; put one wav on track 1")

    ticks = int(round(max(length_beats, 1.0) * project.ppq))
    # replace whatever the template had: only our stems belong in the result
    items = []
    for idx, ch in enumerate(channels):
        item = copy.deepcopy(proto)
        item["position"] = 0
        item["item_index"] = int(ch.iid)
        item["length"] = ticks
        item["track_rvidx"] = 499 - idx
        item["start_offset"] = 0.0
        item["end_offset"] = 0.0
        items.append(item)
    ev.value = items

    # --- notes ---
    targets = _pattern_targets(project)
    if notes:
        _write_notes(project, notes, pattern_name, project.ppq,
                     pattern=targets[0] if targets else None)
    if drum_notes:
        if len(targets) > 1:
            _write_notes(project, drum_notes, drum_pattern_name, project.ppq,
                         pattern=targets[1])
        elif targets:
            # only one pattern carries notes: keep the drums there too
            _write_notes(project, drum_notes,
                         pattern_name if notes else drum_pattern_name,
                         project.ppq, pattern=targets[0], append=bool(notes))

    pyflp.save(project, out)
    return {"path": out, "channels": [c.name for c in channels],
            "items": len(items), "bpm": bpm}


def _notes_event(pattern):
    for e in pattern.events:
        if int(e.id) == int(PatternID.Notes):
            return e
    return None


def _pattern_targets(project):
    """Patterns that already carry a Notes event (FL only writes it once a
    pattern has a note, so we can extend those and nothing else)."""
    return [p for p in project.patterns if _notes_event(p) is not None]


def _write_notes(project, notes: list[NoteEvent], pattern_name: str, ppq: int,
                 pattern=None, append: bool = False) -> bool:
    if pattern is None:
        targets = _pattern_targets(project)
        if not targets:
            return False
        pattern = targets[0]
    try:
        pattern.name = pattern_name
    except Exception:
        pass

    events = _notes_event(pattern)
    if events is None:
        return False

    rack = 0
    try:
        rack = int(getattr(project.channels[0], "iid", 0))
    except Exception:
        pass

    built = [] if not append else list(events.value)
    try:
        from pyflp.pattern import _NoteFlags  # type: ignore[attr-defined]

        no_flags = _NoteFlags(0)
    except Exception:
        no_flags = 0
    for n in notes:
        built.append({
            "position": int(round(n.start_beats * ppq)),
            "flags": no_flags,
            "rack_channel": rack,
            "length": max(1, int(round(n.length_beats * ppq))),
            "key": int(n.pitch),
            "group": 0,
            "fine_pitch": 0,
            "_u1": 0,
            "release": 0,
            "midi_channel": 0,
            "pan": 64,
            "velocity": max(1, min(127, int(n.velocity))),
            "mod_x": 0,
            "mod_y": 0,
        })
    events.value = built
    return True
