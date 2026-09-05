# Note save and exit policy

Case notes in automatic mode and entity notes save after their existing debounce
(one second for cases, five seconds for entities). Leaving edit mode, including
entity Cancel or Escape, flushes pending notes immediately. Cancel still cancels
other entity form edits; it does not discard notes that autosave owns.

Entity Close waits for pending notes to save. If saving fails, the dialog stays
open with the text and error visible; Close can retry. Re-entering edit mode also
retains failed notes so Save Changes can retry them.

Hiding an editor through its parent or unmounting starts a final save of pending
notes before the editor is destroyed. This is best effort: Vue cannot wait for
asynchronous unmount work, and browser shutdown, reload, network failure, or
process termination can prevent persistence. There is no durable local draft or
automatic retry loop after unmount. Switching between embedded and fullscreen
views retains the same editor and does not end the editing session.

Untouched notes, including empty notes and HTML normalized by the editor, do not
create writes on exit. Saves are serialized per editor. An exit joins an
in-flight save of the same content; newer content waits for it. Failed saves do
not advance the saved baseline. A later edit or exit can retry.

Selecting another entity creates a separate editor and save queue, flushing the
previous editor without allowing its pending notes to reach the new entity.

Entity Save Changes participates in the same write queue as notes. It cancels
the pending debounce, waits for any active autosave, and acknowledges its notes
before leaving edit mode. Notes typed while the form is saving are saved
afterward using the updated entity fields.

Manual-mode case notes remain parent-owned. The editor emits changes immediately
but never writes to the case service on debounce, edit-mode exit, or unmount.
The case dashboard currently uses this manual mode.

Regression coverage lives in the real-editor `NoteCompatibility`, `NoteEditor`,
and `EntityNotes` component tests, with focused composable tests for their
existing public APIs.
