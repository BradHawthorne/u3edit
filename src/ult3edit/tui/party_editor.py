"""TUI party state editor: form-based field editing for PRTY file."""

from ..save import PartyState
from .form_editor import FormField, FormEditorTab


def _party_fields(party):
    """Generate FormField list for editing party state."""
    return [
        FormField('Transport',
                   lambda: party.transport,
                   lambda v: setattr(party, 'transport', v)),
        FormField('X',
                   lambda: party.x,
                   lambda v: setattr(party, 'x', int(v)),
                   fmt='int'),
        FormField('Y',
                   lambda: party.y,
                   lambda v: setattr(party, 'y', int(v)),
                   fmt='int'),
        FormField('Party Size',
                   lambda: party.party_size,
                   lambda v: setattr(party, 'party_size', int(v)),
                   fmt='int'),
        FormField('Slot IDs',
                   lambda: ', '.join(str(s) for s in party.slot_ids),
                   lambda v: setattr(party, 'slot_ids',
                                      [int(x.strip()) for x in v.split(',')[:4]])),
        FormField('Location',
                   lambda: party.location_type,
                   lambda v: setattr(party, 'location_type', v)),
        FormField('Sentinel',
                   lambda: f'${party.sentinel:02X}',
                   lambda v: setattr(party, 'sentinel', int(v, 0)),
                   fmt='hex'),
    ]


def make_party_tab(data, save_callback):
    """Create a FormEditorTab for the party state."""
    party = PartyState(data)

    def get_save_data():
        return bytes(party.raw)

    # Wrap in a single-record list for FormEditorTab
    return FormEditorTab(
        tab_name='Party',
        records=[party],
        record_label_fn=lambda p, i: f'Party State ({p.transport}, {p.party_size} members)',
        field_factory=_party_fields,
        save_callback=save_callback,
        get_save_data=get_save_data,
    )
