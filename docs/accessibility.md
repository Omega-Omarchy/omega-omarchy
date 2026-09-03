# Accessibility

Shipped in this alpha:

- Keyboard-only and controller-only first-chapter routes are implemented;
  gamepads hot-plug, multiple pads aggregate, and D-pad/stick edges drive menus
  and movement combos. Physical controller qualification is still required.
- Pause → Controls opens a live remapping screen at every fidelity. Keyboard
  actions have independently editable primary and alternate keys; controller
  actions bind physical buttons. Conflicts swap the displaced binding instead
  of making one press trigger two actions; an empty alternate cannot erase a
  required primary binding. Selected bindings and reset-all are available from
  keyboard or controller, and Escape/D-pad Left cancel capture.
- Remaps are used immediately by traversal, menus, combat, editing, loadout,
  customization, and HUD prompts. Prompts follow the most recently active input
  device. Remaps persist through save/load and world rerolls without affecting
  deterministic world identity. F1/F2/F3/F4/F5/F6/F7/F8/F9/F10 remain reserved for private-alpha
  QA and cannot be captured.
- Reduced-motion installer profile disables CRT animation
- Precision-assist installer profile / Limitless exact component adds coyote/buffer
- Combat and installer copy on screen
- F5 can force the OMARCHY edit for QA; the deterministic fixture places a
  reachable optional logo on its upper route, so F5 is not required

Stick axes and D-pad directions retain their conventional navigation mapping;
the current screen remaps gamepad action buttons. Physical controller
qualification is still required.

Future work: remappable controller axes/hats, high-contrast theme, text scale
slider, and hold-to-repeat.
