# Immediate recipe learning, producer commands and friend counters

## Native recipe update

The learned recipe was saved correctly and appeared after changing maps
because the character bitmap was correct. The immediate message selected
the wrong handler: S2C001D receiver5F0EF0 indexes its table at17416 (`0x4408`),
while recipe handler601B50 is installed at17592 (`0x44b8`). Its index is11.
The old93 used the S2C0013 table base16104 and never invoked recipe learning.

Blueprint use and station refresh now send extended attribute11. This updates
the client's recipe bitmap and native recipe lists without changing maps or
recreating the Manufacture window. Previously learned recipes remain saved.

## GM commands

```text
/recipes all
/recipes weapon 200
/recipes armor 200
/recipes sewing 200
/recipes craft 200
/recipes cooking 200
```

`/recetas` is an alias. The optional level caps the recipe's required skill
level; its default is1000. Learning persists atomically, preserves inventory,
updates the client immediately and reports the number of newly learned
recipes. Manufacturing still checks the actual skill, materials and station.

The manufacturing path additionally resolves available equipment quality
tables through serv_drop.xml instead of rejecting every recipe with
`參考掉寶=是`. Wood Bow recipe19, for example, produces item602,158 or162 with
weights9,159,210 /820,280 /20,510 out of10,000,000. The table ID232 is never
delivered as an item. Missing original tables remain blocked before spending.

## Orders from gathering

The original material.xml order drops are already in materiales.json and
the real gathering roll. There is no added flat5% chance. Copper material1
has total weight1000: ordinary copper900, rare material15, orders886/887/897/898
at5 each and no output65. Thus an order replaces that attempt's normal output
with a combined2% chance. Other resources have their own weights. Orders are
present for Dig, Lumber, Collect and Fishing and are granted as normal inventory
items. Order886 requests30 Copper Ingots, as specified in order.xml.

## Director Wolay

The generic mission offer still proposed tutorial quest100 to graduates with
incomplete tutorial history. Acceptance was blocked elsewhere, but its
dialogue10004 hid Wolay's normal return menu. Student missions are now filtered
out of available offers for graduated characters. Wolay shows5079 with5080/5081
and returns the character to their current faction city. New Heaven characters
retain their original registration flow; graduation data is not reset.

## Friend counters

S2C0028 receiver570000 always moves the friend to its online collection, even
when status10 makes the label read “offline”. This caused `online(2)` with an
offline-labelled friend. Actual offline notification is S2C002E, registered
at1968+46*16 (`0xa90`), receiver571AD0. Its full packet is
`[u16 0x002e][u32 self_char_id][u32 friend_char_id]`.

Offline synchronization and disconnect notification now use that packet.
Closed connections/characters outside the world are excluded from online
lookup. New online contacts use normal status0 instead of hardcoded busy1.

## Verification

Temporary-database tests cover immediate native recipe updates, GM branch and
level filtering, duplicate learning, transaction rollback, original quality
weights, actual gathering drops, all four graduated faction exits, ungraduated
registration, and native online/offline collection transitions.

Final targeted integration run: **177 passed**,1 existing asyncio deprecation
warning, in100.63s. Required core/runtime `py_compile` and `git diff --check`
passed. Tests used temporary databases, not live characters.

Changes require loading the updated server process. No live account data,
executable or running server process was modified by this patch.
