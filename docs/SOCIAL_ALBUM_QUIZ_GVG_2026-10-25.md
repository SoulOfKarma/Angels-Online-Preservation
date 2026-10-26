# Social, Album, Angel Elementary and League War — 2026-10-25

This batch is implemented and tested against temporary SQLite databases. The
live server and the two game clients have not been restarted. Native graphical
behavior still needs an in-game check; passing packet tests does not establish
that every window renders correctly.

## Player-facing changes

- Love Broadcasting handles the native target-name confirmation and all ten
  item variants. Recipient validation and consumption commit together. Missing
  recipients and repeated confirmations do not consume extra items.
- Daily Events Clerk can exchange the Blue Stall Card. Stall vouchers equip
  the correct hidden card atomically; their native capacities and expiration
  are respected. Event maps permit stalls; regional instances do not.
- Hestia faces right and Party Angel uses Angels' Tutor's down-facing direction.
- Team invitations retain Share/Alone. Alone uses damage contribution for EXP
  and gold and the top contributor for loot; Share retains equal distribution.
- Wraith summons send the cast phase and wait for the XML cast/arrival times
  before appearing. A cancelled cast cannot leave an invisible attacking unit.
- Olympus completion and timed completion achievements persist with the result.
- Periodic Daily EXP and Skill EXP now persist with a receipt for each pulse.
  Re-entry and reconnect cannot replay a pulse; no combat damage/healing packet
  is used to display EXP. Existing faction arrival points, exits, separated
  chest batches and the original chest return are preserved.

## Social protocol

Friends use native C2S0019..0021 and S2C0027..002A. Invitations require an actual,
unexpired consent request bound to both characters. Mutual friends, groups,
online state and contact filters persist. Blocking is rechecked on acceptance.

Mail uses C2S0100..0103/0106/0107 and S2C003B..0040. Text mail and CC validate all
recipients and capacity before committing. Read/delete operations belong to the
mailbox owner. Blacklist/trusted state persists; restoring the blacklist's
graphical list on reconnect still needs client verification. The original text
mail fee was not identified, so this implementation does not charge one.

Chatrooms use C2S0120/0122/0124/0125/0126/0129. Public rooms and private
conversations enforce membership, owner-only kick/transfer and disconnect
cleanup. The native member record contains the Hestia shard ID **16**; putting
the channel subset there prevents the client opening its own room correctly.

Minigames use C2S0010 / S2C001F with nested subtypes. Permanent and 1/7/30-day
cards equip native access slots156..159. Only the host needs the card.
Five in a row, Bingo, Othello and Big-2 validate turns and moves on the server.
Big-2 supports up to four players, private hands, straights, full houses, four
of a kind and straight flushes. The native classifier does not accept a flush
alone. Scores are virtual; these games do not wager character Gold. Server turn
timeouts are not implemented yet; leaving/disconnecting closes the game.

## Album

C2S0016 sub32 opens the actual saved album; sub33 deposits an inventory item.
S2C0156 serializes the expansion mask, eight counts and packed collection cells.
The score follows native705D50 and its category/color tables. Additional item
attributes count toward value. Existing category totals migrate without losing
points. Appearance items use doll themes, apparel type and native base scores.

The inventory item and collection cell commit together. Temporary equipment
and registered furniture cannot be deposited. The 90 collection.xml thresholds
feed the character stat calculation. Expansion coupons/sub34 are still pending;
noncombat bonuses need a separate audit of all EXP/crafting/gathering paths.

## Angel Elementary

The current client has active answer handlers: OnQTAns -> QTSelectAns58FBB0 ->
5D5F50 -> 5D5FC0 -> 5D60F0. Older QTAns1/2/3 bindings are obsolete. No executable
patch is needed.

Recovered data: 200 enabled questions from question.xml, original map502
question.mpc, its arrival/exits and the 30 bufprize.xml rank rewards. Questions
and answers use the native Blowfish/base64 representation. The server decrypts
the selected answer; the clear answer field in C2S0153 is a random decoy.

Registration opens daily at18:45 and the quiz starts at19:00. Thirty questions
last ten seconds each. The server clock determines points. Hearts/stars,
Smart Star and the Blessings Bell are connected. Results, EXP, Skill EXP and
one-time prize receipts persist. Teacher dialogs use original8341..8347.

The original server EXP formula is not in the client. The explicit local
compatibility formula is level² × score for EXP, score for Skill EXP, score/10
for credit, with server multipliers and the Bell's double reward. Top30 item
rewards are original. Finishing leaves the exit portals available.

GM commands:

```text
/quiz start 10
/quiz enter
/quiz status
/quiz finish
/quiz stop
```

## League War

Original client evidence:

- gvg.lua and wnd05/wndtext05: Ctrl+W; Lv6 league and leader registration.
- Wednesday21:00–21:30; Sunday17:00–17:30 and22:30–23:00, server local time.
- Maps265..272 supply terrain, arrival tags, two waiting-area portals, two
  statues and the mine positions. material639 yields item37362.
- Native UI requests: C2S0016 sub64..67,0158/0159,015A and015B.
- Responses0173..0177. War Plan rows contain dates/time slots, not map names:
  YYYYMMDD at row+12, signup minutes at+16/+20, battle minutes at+24/+28.
- Battle attributes use the long001D table index63; subtype6 is the battle
  identity, not remaining seconds. Subtypes2/3 are the two scores.

Registration allows sixteen leagues. At the start, opponents are paired near
their existing rank and assigned randomly among the eight maps. Entry opens
after registration ends. Both teams receive PvP state and colored circles.
Guild membership is checked again for attacks, entry and construction actions.
Deaths return to the league's arrival area after five seconds without the
ordinary world PvP EXP penalty. Friendly statues/mercenaries are protected.

The current [USERJOY League War guide](https://aog.userjoy.com/en/news_con.php?c=09&news=11150)
is a cross-edition mechanics reference, not proof of every IGG setting. In
particular this client's Lv6 rule is retained. Its statue/resource behavior
and the local mercenary controller were checked against that guide. The
original five-minute waiting barrier, pet scoring, default-win settlement and
full seasonal eligibility/48-hour expiration rules remain outside this batch.

Mercenaries use the original Mercenary monster rows, selecting the highest
available level at or below the best production skill. Mechanism and Drive
are excluded from that calculation. Their basic movement and combat run once
per shared map tick. Native per-mercenary combat spells are not reproduced yet.
LW-Barrel37388 is available only to producers without combat skills and is
removed on leaving. The field HP bonus is removed when changing maps.

### Redemption proven by Karma's screenshots

| Original items | Reward Points |
| --- | ---: |
| Valor / Valoria Military pieces48007..48014 | 300 each |
| Victory Military Baton48015 | 600 |
| Victory Military Cape48016 | 300 |
| Lv13 / Lv14 Battlefield Badge48017/48018 | 150 / 200 |
| Mau Mask48049 / Killer Doll48050 | 100 each |
| Bound22-star tools43301..43304 | 20 each |
| Double EXP / Skill EXP48051/48052 | 10 each |
| Ultra potion boxes48072/48073 | 5 each |

The fixed box contents are20 potions48053/48054, established by their original
tooltips; missing server-only drop rows no longer prevent opening those boxes.
Redemption commits all items and the wallet debit together and reports success.

### Explicit local reward balance

Karma authorized provisional outcome points and rewards. These editable values
in plantillas/league_war.json are **local settings**, not recovered IGG formulas:

- Battle outcome Repute: win30, draw15, loss5.
- Participant Reward Points: win120, draw80, loss40.
- Weekly top3 additional points:1000/750/500.
- Four-week seasonal top3 additional points:4000/3000/2000.
- A solo field or cancelled round does not pay battle rewards.
- Previous-period claims require actual participation; newcomers cannot claim
  the earlier team's results. Claims and settlements have persistent receipts.
- Registration defaults to15 minutes. A local cap of three active mercenaries
  per player limits repeated summon requests.

Commands for two test league leaders (both leagues must be Lv6):

```text
/gvg start 30 1800
/gvg register
# Run register on the second leader too; wait30 seconds.
/gvg enter
/gvg status
/gvg finish
/gvg stop
```

`start` opens registration; `finish` settles results; `stop` cancels without
rewards. Ctrl+W is the normal register/enter/redeem/ranking path. Changing the
local configuration requires loading the new server process.

## Validation

The integrated suite covers native request routing, temporary SQL persistence,
duplicate confirmations, wallet/inventory rollback, consent/ownership, complete
minigame matches, encrypted quiz answers, event pulses and competition results.
Final run: **304 passed**, with17 existing asyncio deprecation warnings, in37.52s.
Core modules and all newly added runtime modules passed `py_compile`;
`git diff --check` also passed. REA was closed normally after the investigation.
Compile the four core modules before starting the server. No account reset,
live reward grant, executable modification, commit or push was performed by
this batch.
