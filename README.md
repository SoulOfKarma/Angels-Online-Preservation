# Angels Online — local server

***English** · [Español](README.es.md)*

Reverse-engineered network protocol for **Angels Online** (IGG, shut down in
February 2026, client 8.5.1.0) and a server that speaks it, built from the client files and
from traffic captures.

This is not a complete emulator. It is the **documented protocol** plus a
server that goes as far as it goes: you can create a character, run the
tutorial, pick a class, fight and buy. What is missing is listed below,
without sugarcoating.

---

## Actual state

**Works**

- Login, character creation and selection, saved to disk
- Entering the world, movement, and changing maps
- Angel Raphael's tutorial: picking a class, getting the gear, the transfer
- Full inventory: equip, unequip, move between slots, durability
- Stats computed from `item.xml` (gear actually adds up)
- Angel Lyceum drawn: 52 NPCs, 81 monsters and 158 resources appear at their
  real positions, taken from the client's XML files

**Partly**

- Combat: you can target a monster and hit it, and the server tracks each
  monster's health, but **the damage number doesn't show and the loot never
  arrives**. The messages are sent and match the real server byte for byte,
  so something else is missing that hasn't been identified yet
- NPC dialogue: 17 of the Lyceum's 52 NPCs have their text and options, but
  **picking an option closes the box** instead of continuing
- Shops: the purchase message works and deducts the gold, but **the shop
  window never opens** from the dialogue, so in practice you still cannot
  buy anything while playing

**Does not work**

- NPCs and monsters are static: they don't move, don't react, don't attack on
  their own and don't respawn when killed
- Resources can't be gathered
- Boxes can't be opened: the "use item" message is missing
- The three starting spells are missing, the ones bound to F1-F3
- No experience and no levelling up
- Characters can't be deleted
- Floor teleport zones don't work (the map change itself does, but the server
  has to trigger it)
- Five of the Lyceum's NPCs were never captured and are missing
- Passwords are **not validated**: the auth block hasn't been decrypted

---

## Running it

You need **Python 3.10 or newer** and the Angels Online client installed.
Tested against client **8.5.1.0**; the captures the protocol comes from were
taken with an **8.6.0.8**, and both speak the same thing.

1. Point the client at your machine, in its `server.xml`:

   ```xml
   <伺服器 名稱="Local" 編號="16" 選擇="100"
           ip="127.0.0.1" port="16768" 分流="2"
           fip="127.0.0.1" fport="21238" />
   ```

2. Start the server:

   ```
   ./correr_servidor.sh        # Linux, macOS, Git Bash
   correr_servidor.bat         # Windows
   ```

3. Open the client and log in with any username. The account is created for
   you.

Every session is recorded under `logs/sesiones/`, which is what you use to
debug.

### Environment variables

| Variable | What it does |
|---|---|
| `AO_TILE` | Spawn tile in Guide Palace (default `82,83`) |
| `AO_TILE_LYCEUM` | Spawn tile in the Lyceum (`152,74`) |
| `AO_DURABILIDAD` | Multiplies the durability of everything the server hands out |
| `AO_SECUENCIA_COMPLETA` | Sends the whole captured entry sequence, for comparison |

---

## Layout

```
proto/        the protocol: framing, ciphers, message codec, LZO
server/       the server: login, world, inventory, combat, dialogue
server/plantillas/   blocks measured from real traffic, as JSON
tools/        capture proxy and analysis tools
docs/         everything that was worked out, and how it was verified
```

**Read `docs/01_HECHOS_VERIFICADOS.md` before touching anything.** It is 1750
lines covering every finding, how it was checked, and the mistakes made along
the way with their diagnosis. That last part is worth more than the code:
several things were taken as true from a single sample and turned out to be
wrong.

The documentation is in Spanish. The code and the commit history are too.

---

## Known issues, with screenshots

Each one is under `docs/capturas/`.

### 1. The skill panel comes up half empty

![skills](docs/capturas/1-skills-vacias.png)

The skill panel shows the chosen class's row and question marks for the rest.
The three starting spells are also missing, the ones bound to F1-F3: the real
server sends them with message id 425 and they aren't sent here. Which three
they are depends on the weapon you pick: the character in the screenshot uses
a spear, so his would be Basic Attack I, Bloody Song I and Endless Energy I
(ids 801, 802 and 803 in `magic.xml`, the three level-1 entries with
`技能限制1="槍術技能"`). With a sword they would be Slicing Hit I, Swiftness
Song I and Injury Cure I, ids 601 to 603.

### 2. NPCs stand still and say nothing

![idle npcs](docs/capturas/2-npcs-quietos-sin-dialogo.png)

House Pickets and friends wander around in the real game and have a default
line. Here they are planted and mute: there's no NPC movement, and 35 of the
Lyceum's 52 have no text assigned.

### 3. Boxes don't open

![boxes](docs/capturas/3-cajas-no-abren.png)

They're handed out correctly and the tooltip is right (read from `item.xml`),
but clicking them does nothing. The "use item" message is missing and doesn't
appear in any capture. In-game, opening the level 5 box gives you the level 15
one, that one the level 25, and so on.

### 4. The shop window doesn't open

![shop](docs/capturas/4-tienda-no-abre.png)

The Shopkeeper's dialogue shows both options, but choosing "Tell me about the
buying and selling of goods" closes the box instead of opening the shop. Buying
itself **does work** (`0x0027` is implemented): what's missing is knowing which
dialogue each option leads to.

### 5. Portals don't work

![portals](docs/capturas/5-portales-no-funcionan.png)

Floor teleport zones are visible but do nothing, and sometimes the character
gets stuck against them. Changing maps **is** implemented (`0x000C` + `0x0009`);
what's missing is what the client sends when stepping on the zone.

---

## What is deliberately skipped

So the server runs without a database or a sign-up flow, some things aren't
checked. These aren't bugs, they're decisions:

**Accounts create themselves.** Log in with any username and it gets saved to
`data/cuentas.json`. If you want to set one up by hand, it's plain JSON:

```json
{
  "cuentas": {
    "youruser": {
      "password": "whatever",
      "personajes": []
    }
  }
}
```

**Passwords are NOT validated.** Anything gets you in. The username is read
from the auth message, but the block carrying the password hasn't been
decrypted, so there's nothing to compare against. Finding that field was tried
twice and both attempts were wrong: one rejected valid logins, the other
accepted everything because the offset turned out to be a client-side
constant. It's documented in `server/cuentas.py`.

**There's no sign-up, no email, no recovery.** It's a local server.

### Visual glitches on reconnect

Some things look wrong until you log out and back in. Server and client end up
agreeing, but the client doesn't refresh on the spot:

- On a fresh character, gear sometimes doesn't show until you reconnect
- Music cuts out when changing maps
- The gear panel can be left with an extra slot drawn

Nothing gets corrupted: what's in `data/cuentas.json` is always correct.

---

## How to help

What's missing most isn't programming: it's **captures**.

Almost everything that doesn't work is missing because it was never recorded.
The proxy sits between the client and a working server, and logs both
directions with timestamps:

```
python tools/proxy.py --server-xml "path/to/server.xml"
# play for a while, doing whatever you want to capture
python tools/proxy.py --server-xml "path/to/server.xml" --restaurar
python tools/correlacionar.py --novedades
```

Two lessons that took several rounds to learn:

- **A capture only contains what you had on screen.** To populate a map you
  have to walk all of it, not stand in one spot.
- **Leave a couple of seconds between actions.** If they pile up, there's no
  way to tell which reply belongs to which request.

What would help right now, most useful first:

1. **Killing a monster from the first hit to the loot.** The damage number and
   the loot don't show up here, and the capture in hand doesn't cover the whole
   exchange.
2. **Picking dialogue options** on several different NPCs. Five or six cases
   would settle both the shop and Cupid's respawn point.
3. **Deleting a character** that is past its protection period.
4. **Crossing a floor teleport zone.**
5. **Gathering a resource** with the right tool equipped.
6. **Levelling up**, to see what the server sends.

### Any kind of help

Everything is useful, and you don't need to know reverse engineering:

- **Traffic captures.** This is what's missing most. See above.
- **Code.** Pull requests are welcome. If you touch the protocol, say what you
  checked it against: this project rests on every claim having its
  verification behind it.
- **Client data.** If you find something in the `.xml` or `.pak` files that was
  written off as impossible here, say so. It has already happened twice that
  the data was right there.
- **Bug reports.** The server log plus what you did in the client is enough.
  The `logs/sesiones/` folder from that session helps a lot if you can share it.
- **Translations.** The documentation is in Spanish.
- **Just playing and telling us what breaks.** Half an hour in-game finds
  things that reading the code doesn't.

If you don't know where to start, open an issue and ask.

Before recording anything, check whether the data is already in the client's
XML files. It happened twice: spawn points were in `jumpmap.xml` and dialogue
in `msg.xml`, and captures were requested for things already on disk.

---

## Credits

This server was written from scratch, but it didn't start from nothing.

- **[AngelsOnlineDev/AO](https://github.com/AngelsOnlineDev/AO)** — the project
  that opened the way. No code was copied from it, but it was studied, and
  reading its log produced the finding that unblocked this whole project: the
  world redirect is sent **in reply to `0x0006`**, not after authentication.
  Weeks were spent stuck on that screen comparing bytes that were already
  correct; the problem was timing, not content.
- **Squirrel**, from RageZone — for trying first and leaving a trail. Someone
  having started and written something down, even without finishing, saves you
  the work of finding out which doors aren't worth opening.

And to whoever kept the client and its `.pak` files around. Without them there
would be nothing to rebuild: a good part of what works here came from reading
the game's own `.xml` files, not from traffic.

---

## Notice

Angels Online belongs to IGG. This is preservation work on a game that no
longer exists, done against a client anyone can install.

**Nothing of IGG's is included here**: not the client, not its data, not the
decompiled binary. The server reads the `.xml` and `.pak` files from a client
you already have; without one it does nothing and is of no use.

**No traffic captures are included either.** The ones used carried account
names and other people's public chat. The analysis lives in `docs/`; the raw
bytes aren't needed for anything. If you contribute captures, check the same
before uploading them.
