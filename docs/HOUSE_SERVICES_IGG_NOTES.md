# House services: evidence and remaining verification

Updated 2026-10-16. Applies to AO 2 and the IGG extracted client, not Global.

- `npc.xml` identifies NPC 2603 but its sprite 40015 is the n015 placeholder.
  `npc.obd` identifies NPC1062 / house maid as sequence 40262, npc/n262.
  The installed client's update3.pak actually supplies 40262_wait.spr, with
  ONLY w014/w016, w024/w026 and w034/w036. Direction 6 selects missing *5
  and produces a name/shadow without a body. Direction 3 restored visibility
  but the user's screenshot confirmed the wrong facing; use opposite diagonal
  direction 7 toward the doorway/down-left. All greetings and service replies
  now share portrait 1062, replacing leftover NPC182 portraits,
  retaining (44,82) and the working doorway portal. The raw assets were
  decoded and visually checked with tools/audit_house_visuals.py, not merely
  inferred from the XML name. No client assets were modified.
- Crash `C:/AO/Angels Online/err6ad2dd23.dmp` (23:27): access violation
  0xC0000005 at 0x5EF422, in sub_5EF410 called by S2C 0x000F handler
  sub_5F0350. The server sent a six-byte <HI> as a removal, but this is a
  46-byte named-object update. House services and disconnected outdoor houses
  now use seven-byte 0x0007 despawns (sub_5ECA40), not truncated 0x000F.
- Editor re-entry refresh: 0x013E creates widgets; a following 0x001A with
  only slot 376 upserts the equipped deed and calls sub_66C880(...,1), filling
  owner and icon. 0x001B alone does not call that refresh. House name remains
  the separately saved editable field at 0x013E+7. Leave callbacks are guarded
  against reopening/new transitions. Deed changes reject resizing inside the
  house and exceeding a smaller house's furniture capacity.
- `default.mpc` UPDATE18: five manufacturing objects (events 20..24), five
  harvesting objects (material IDs 281/293/305/317/329), pet machine 60155 at
  (27,31), and monster machine 60155 at (85,31). The mailbox is 62358, not
  the pet-training machine. Original gates: manufacturing house level 2,
  pet slots level 3, monster slots level 6; services stop at zero cleanliness.
- IGG `sub_606950`, registered at base 1968 + 16 * 0x4B: S2C 0x004B opens
  manufacturing with a one-byte category. `sub_606EA0` reads S2C 0x004C as
  success byte followed by recipe u32; C2S 0x0036 carries that recipe u32.
  Crafting validates the XML skill/level and materials, waits the XML time,
  then grants the XML output and acknowledges the queued unit.
  Recipes referencing a random drop table are refused before taking materials;
  their reward tables are not treated as direct inventory item IDs.
- `monster.xml`: mercenary families and their real models/stats, including
  later level brackets. Selection currently uses the highest available level
  not exceeding the character's level. The precise additional house-level
  scaling/cap is not specified in the client and remains unverified.
- `item2.xml`: 10581 requires level 30, has duration 480 minutes and explicitly
  says use WITHOUT consuming. The real item persists for eight wall-clock
  hours from receipt; its expiry and next permitted summon are item metadata,
  preserved on moves/reconnect. The expiry timestamp is encoded at entry +47
  (native item +46, tooltip sub_5C3710), without changing entry length.
  Spell 2254 specifies a 180-second cooldown and a 3600-second summon lifetime.
  Using the item summons, death permits resummoning after cooldown, and map
  reload dismisses the mercenary without consuming the token. No independent
  summon skill is granted. Old consumed contracts recover a token with only
  their remaining lifetime; invisible old token slots can still be recovered.
- Resources select material.xml's twelve house tiers per category by character
  level, capped at the last defined tier (111). Their sprite, name and actual
  gathered outputs all select the same material. Name updates are full-length
  0x000F packets, and depletion is private to the house session, not all houses.
- Cooking/tailoring and safe now clear wire flags bit 2: sub_5EF410 maps it
  to SP_ATTRIB_MIRROR (0x00800000), the real isometric-facing flip. Changing
  the direction byte did nothing to these single-view static sprites.
  Other objects/portals retain their original flags. The follow-up screenshot
  showed weapon forge too high/touching armor: it is now (10,24), 32 px left
  and 96 px down from (11,27), leaving a gap. The final one-tile forward
  adjustment aligns its rear edge with the armor forge's isometric line.
  Cooking is now (12,19), 32 px
  left/up from (13,18), separated from the unchanged tailor station.
  Mailbox stays at (32,31): left/up in
  the client's coordinate system (+Y is up), away from the passage. The
  duplicate Suft NPC/nameplate is removed. Pet/monster egg dialogs have no
  portrait, including explanations and locked-level responses.
- Safe: personal storage now uses the existing 0x004E bank hydration path.
  Guild storage is explicitly unavailable: the project currently has no guild
  membership/storage backend (event context has tiene_guild returning False).
- Monster Egg category `怪物蛋` resolves its monster through `動態資料1`.
  Its lifetime is persisted with the item metadata, so moving the item or
  reconnecting does not restart its clock. Spawn/respawn is limited to unlocked
  owner slots and disabled while decorating; the regular map respawner does
  not resurrect removed eggs.
- `sub_66A8B0`: the cleanliness label shows +10% at 90..100 and +20% above
  100, rather than cleanliness/10. This is not a character EXP modifier.
- Soap Powder: original map action 93 and item description specify +10.
- Cleanliness decay is configured as one point per 180 seconds connected
  **per character**, as requested. This interval still needs an original IGG
  capture; it is not represented as a verified XML constant. Partial online
  intervals persist; daily rollover and offline time do not subtract points.
- Eilian spells 2292..2295 last 180 minutes. Tier I explicitly lists +5
  percentage points for the fourth enhancement and +4 for the first piercing;
  tier II lists +10/+8. These are connected to the equipment improvement
  functions, with probabilities capped at 100%. They never award EXP.
  The general enhancement probabilities remain the project's pre-existing
  approximation. Exact tier III/IV percentages and Lucky Hammer's additional
  attribute calculation still require evidence; no values were invented.
- Suft Submit now resolves all five categories through the latest order.xml:
  one owned receipt plus the exact finished-product quantities, paid with XML
  EXP, money, honor credits and optional bonus probability (including decimal
  percentages). It requires owner, cleanliness and house level 4 (msg 7852).
  Inventory deltas and rewards commit together under BEGIN IMMEDIATE against
  the exact account/character; stale/replayed orders fail without consumption.
  No character snapshot replaces unrelated inventory or character fields.
  Resulting level/rank are derived from the normal EXP/credit curves. Bonus
  rewards may reuse a slot freed by the delivery. No receipt-free resource
  exchange is implied by these five producer-order options.
- Automatic pet-training EXP remains unimplemented; opening the existing pet
  window must not be confused with completed automatic training calculations.

Validation: `tools/test_house_services.py` exercises the online clock,
old token recovery, original XML data, machine routing, crafting materials,
egg lifetime metadata, token lifetime/tooltip/cooldown/reconnect, editor
reopening, valid despawn sizes, resource tiers/names and portrait-free dialogs.
The legacy improvement persistence test now uses an isolated temporary SQLite
database, never a real account. Visual placement and live client interaction
still require an in-game check after restarting the server.

2026-10-17 verification: 57 tests pass across tools.test_house_services,
tools.test_house_system and tools.test_producer_orders. Delivery persistence
tests use synthetic characters in a temporary SQLite database, including
replay rejection and preservation of an unrelated character.
