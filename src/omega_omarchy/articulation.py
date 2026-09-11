"""Small deterministic three-joint sprite rig, in logical screen pixels."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ArmPose:
    shoulder: tuple[float, float]
    elbow: tuple[float, float]
    wrist: tuple[float, float]
    angles: tuple[float, float, float]
    closed: bool


def custodian_x(x: float, tick: int, *, right: bool = False, staging: str = "transfer", reduced: bool = False) -> float:
    """Enter with departing orbs; malfunction around a fixed home, never drift."""
    if staging == "orb-machine":
        progress = max(0.0, min(1.0, (tick - 144) / 180))
        if reduced:
            progress = float(tick >= 144)
        progress = progress * progress * (3 - 2 * progress)
        outside = 392 if right else -72
        return outside + (x - outside) * progress
    if staging == "corrupt" and not reduced:
        phase = tick + (29 if right else 0)
        burst = max(0.0, math.sin(phase / 17))
        return x + burst * (5 * math.sin(phase / 3.1) + 2 * math.sin(phase / 1.7))
    return x


def custodian_pose(x: float, feet_y: float, tick: int, *, right: bool = False, reduced: bool = False,
                   corrupt: bool = False) -> ArmPose:
    phase = 0.0 if reduced else tick / 42.0 + (1.7 if right else 0)
    shoulder_angle = -52 + (0 if reduced else math.sin(phase) * 7)
    elbow_angle = 98 + (0 if reduced else math.sin(phase * .73 + .6) * 9)
    wrist_angle = -12 + (0 if reduced else math.sin(phase * 1.13) * 12)
    angles = (shoulder_angle, shoulder_angle + elbow_angle,
              shoulder_angle + elbow_angle + wrist_angle)
    if corrupt and not reduced:
        phase = tick + (29 if right else 0)
        angles = (-90 + 48 * math.sin(phase / 5.3),
                  -90 + 65 * math.sin(phase / 4.1 + 1),
                  -85 + 105 * math.sin(phase / 3.3))
    if right:
        angles = tuple(180 - angle for angle in angles)

    def end(point: tuple[float, float], length: float, angle: float) -> tuple[float, float]:
        angle = math.radians(angle)
        return point[0] + math.cos(angle) * length, point[1] + math.sin(angle) * length

    shoulder = (x, feet_y - 40)
    elbow = end(shoulder, 27, angles[0])
    wrist = end(elbow, 24, angles[1])
    period = 22 if corrupt else 160
    return ArmPose(shoulder, elbow, wrist, angles, False if reduced else (tick + (45 if right else 0)) % period >= period * .625)
