# SEO / structured data rules

## One SETTWOR entity, one @id
- The artist entity is defined ONCE, on https://settwor.com.pl/ , as a `MusicGroup` (one type only, never `Person`, no `jobTitle`) with the single `@id` `https://settwor.com.pl/#artist` and `sameAs` to every profile.
- CDRA never defines or re-types that entity. In its JSON-LD, `creator` (and `publisher` on the home page, `byArtist`, `about`) is only `{"@id": "https://settwor.com.pl/#artist"}`. Ledgertone references it the same way (`creator` or `founder`).
- `scripts/release.py check` fails if a CDRA page defines a node with that `@id` or if `creator` is not that `@id`.
- Google says no special machine-readable files or markup are needed to appear in Search, including AI features, and that `llms.txt` does nothing (helps or hurts nothing). So the markup is for disambiguation, not for a ranking boost, and no `llms.txt` is made.

## Owner side (settwor.com.pl, not part of this archive)
Put this block in the home page of settwor.com.pl (`src/pages.json` -> `artist.same_as` is the master list):

```json
{
  "@context": "https://schema.org",
  "@type": "MusicGroup",
  "@id": "https://settwor.com.pl/#artist",
  "name": "SETTWOR",
  "url": "https://settwor.com.pl/",
  "genre": [
    "Brazilian Funk",
    "Phonk"
  ],
  "sameAs": [
    "https://open.spotify.com/artist/5BD8hsAGp1fwJKcnlQWjGf",
    "https://music.apple.com/us/artist/settwor/1526983418",
    "https://music.youtube.com/channel/UCr8rodS7kLD36B_8B4028kg",
    "https://www.pandora.com/artist/settwor/ARZ4r4pddcgPq3c",
    "https://youtube.com/c/settwor",
    "https://instagram.com/settwor",
    "https://settw0r.t.me",
    "https://www.last.fm/music/SETTWOR",
    "https://www.shazam.com/artist/settwor/1526983418",
    "https://musicbrainz.org/artist/895afe57-dd9f-40f1-a761-b7db0b88e6d4",
    "https://www.musixmatch.com/artist/SETTWOR-1",
    "https://genius.com/artists/Settwor",
    "https://www.deezer.com/artist/103506422",
    "https://www.amazon.com/music/player/artists/B08FH5CSWV/settwor",
    "https://www.tiktok.com/@settwor",
    "https://music.youtube.com/@SETTWOR",
    "https://www.youtube.com/@SETTWOR"
  ]
}
```
