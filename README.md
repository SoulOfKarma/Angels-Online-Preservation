# Angels Online — local server

***English** · [Español](README.es.md)*

Reverse-engineered network protocol for **Angels Online** (IGG, shut down in
February 2026) and a server that speaks it, built from the client files and
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
- Buying from shops
- Angel Lyceum populated: 52 NPCs, 81 monsters and 158 resources in place
- Combat: hitting, being hit, seeing the damage number, killing and looting
- NPC dialogue with its options

**Does not work**

- NPCs neither move nor react; monsters don't attack on their own and don't
  respawn when killed
- Picking a dialogue option closes the box instead of continuing
- No experience and no levelling up
- Resources can't be gathered
- Characters can't be deleted
- Floor teleport zones don't work (the map change itself does, but the server
  has to trigger it)
- 35 of the Lyceum's 52 NPCs still have no dialogue
- Passwords are **not validated**: the auth block hasn't been decrypted

---

## Running it

You need **Python 3.10 or newer** and the Angels Online client installed.

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

1. **Picking dialogue options** on several different NPCs. Five or six cases
   would settle both the shop and Cupid's respawn point.
2. **Deleting a character** that is past its protection period.
3. **Crossing a floor teleport zone.**
4. **Gathering a resource** with the right tool equipped.
5. **Levelling up**, to see what the server sends.

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
