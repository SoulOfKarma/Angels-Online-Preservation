# House identity and Decorate regression

A legacy house record may contain only `deed_id`/`muebles`, or already have
been serialized with `owner_id: 0`, an empty owner name and `house_name:
"'s House"`. Deserialization defaulted the missing identity to zero and
cached that object under the real character ID. The house window therefore
had no name and C2S0136 correctly rejected decoration because its stored
owner did not match the character.

`casas.obtener_o_crear_casa` now binds loaded and cached houses to the
character/cache key supplied by the caller. It repairs generated default
names, preserves custom house names and prevents a placeholder lookup such
as `Owner_1001` from replacing a known owner's name.

Login's `_sanear_escrituras` persists the repaired identity even when the
equipped deed has not changed. It preserves the house's current deed,
furniture, pets, progress and unknown legacy fields. Other character data
is left to the existing targeted `cuentas.guardar_casa` update. A visitor's
`casa_visitando` is never rebound to the visitor; the normal owner check
still rejects their Decorate request.

Validation:91 tests passed across ownership migration, house services and
scene/production integration. The13 ownership tests also passed in the
separate AO3 test checkout after applying the same source correction. Core
syntax checks passed in both checkouts. No live account record was edited
manually. Loading the corrected server and logging in performs the migration.
