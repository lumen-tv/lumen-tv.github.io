#!/usr/bin/env python3
"""Builds the Lumen demo library under demo/: a pretend Xtream login made of static files.

The Lumen iPhone/iPad app reads https://lumen-tv.github.io/demo (username demo, password demo)
as a static panel: `player_api/<action>.json` instead of `player_api.php?action=...`, and the
`direct_source` link of each film, episode and channel instead of the panel's own stream path.

Everything in it is free to show and play: open movies from the Blender Foundation (CC BY),
films and shorts in the public domain, NASA footage (public domain) and public test streams.
The videos stay where they are (Internet Archive, the streams' own hosts); only small poster
and still images are copied here (demo/img), with their sources in demo/CREDITS.md.

Run from the repository root:  python3 tools/build_demo.py [--images]
--images downloads posters and grabs stills with ffmpeg (slow; needs network). Without it only
the JSON and the guide are rewritten. The guide covers the next 3 weeks from the day it's built;
.github/workflows/demo-guide.yml rebuilds it every week so it never runs out.
"""
import datetime as dt
import hashlib
import json
import os
import subprocess
import time
import sys
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

SITE = "https://lumen-tv.github.io/demo"
OUT = "demo"
UA = {"User-Agent": "LumenDemoBuilder/1.0 (https://lumen-tv.github.io)"}


def ia(identifier, name):
    return f"https://archive.org/download/{identifier}/{urllib.parse.quote(name)}"


def commons(path):
    """`c/c5/File.jpg` → the Wikimedia Commons original."""
    return f"https://upload.wikimedia.org/wikipedia/commons/{path}"


# Films. Plots are our own short summaries. still = seconds into the film for the backdrop.
MOVIE_CATEGORIES = [
    ("1", "Open Movies"),
    ("2", "Silent Classics"),
    ("3", "Mystery & Horror"),
    ("4", "Hollywood Classics"),
]

MOVIES = [
    dict(id=101, cat="1", title="Big Buck Bunny", year=2008, genre="Animation, Comedy", rating=7.8,
         src=ia("BigBuckBunny_124", "Content/big_buck_bunny_720p_surround.mp4"), secs=596, still=95,
         poster=commons("c/c5/Big_buck_bunny_poster_big.jpg"), director="Sacha Goedegebure",
         plot="A gentle giant rabbit enjoys a quiet morning in the forest until three bullying rodents push him one step too far.",
         licence="CC BY 3.0, Blender Foundation"),
    dict(id=102, cat="1", title="Sintel", year=2010, genre="Animation, Fantasy", rating=7.5,
         src=ia("Sintel", "sintel-2048-stereo.mp4"), secs=888, still=200,
         poster=commons("8/8f/Sintel_poster.jpg"), director="Colin Levy",
         plot="A lonely young woman crosses snowfields and cities in search of the baby dragon she once rescued.",
         licence="CC BY 3.0, Blender Foundation"),
    dict(id=103, cat="1", title="Tears of Steel", year=2012, genre="Sci-Fi, Action", rating=6.4,
         src=ia("Tears-of-Steel", "tears_of_steel_720p.mp4"), secs=734, still=290,
         poster=commons("7/70/Tos-poster.png"), director="Ian Hubert",
         plot="In a future Amsterdam, a group of scientists tries to rescue the world from robots by replaying a painful break-up.",
         licence="CC BY 3.0, Blender Foundation"),
    dict(id=104, cat="1", title="Elephants Dream", year=2006, genre="Animation, Sci-Fi", rating=6.6,
         src=ia("ElephantsDream", "ed_hd.mp4"), secs=654, still=160,
         poster=commons("0/0c/ElephantsDreamPoster.jpg"), director="Bassam Kurdali",
         plot="Two men explore a vast, strange machine, and only one of them believes it is alive.",
         licence="CC BY 2.5, Blender Foundation"),
    dict(id=105, cat="1", title="Cosmos Laundromat", year=2015, genre="Animation, Fantasy", rating=7.4,
         src=ia("CosmosLaundromatFirstCycle", "Cosmos Laundromat - First Cycle (1080p).mp4"), secs=731, still=330,
         poster=commons("c/c5/CosmosLaundromatPoster.jpg"), director="Mathieu Auvray",
         plot="A sheep tired of life on a lonely island meets a salesman who offers him a lifetime in a single afternoon.",
         licence="CC BY 4.0, Blender Foundation"),
    dict(id=106, cat="1", title="Spring", year=2019, genre="Animation, Fantasy", rating=7.6,
         src=ia("springopenmovie", "springopenmovie.ia.mp4"), secs=464, still=150,
         poster=commons("0/05/Spring2019PillarPosterBlender.jpg"), director="Andy Goralczyk",
         plot="A shepherd girl and her dog face the ancient spirits of the mountain to bring back the spring.",
         licence="CC BY 4.0, Blender Foundation"),
    dict(id=201, cat="2", title="The General", year=1926, genre="Comedy, Adventure", rating=8.1,
         src=ia("The_General_Buster_Keaton", "The_General.mp4"), secs=4724, still=1500,
         poster=commons("0/0c/The_General_%281926%29_-_Movie_Poster_2.png"), director="Clyde Bruckman, Buster Keaton",
         plot="A train engineer chases his stolen locomotive, and the girl he loves, deep behind enemy lines.",
         licence="Public domain"),
    dict(id=202, cat="2", title="Sherlock Jr.", year=1924, genre="Comedy, Fantasy", rating=8.2,
         src=ia("sherlockjr1924_201909", "Sherlock Jr. - Buster Keaton (1924) HD [720p].mp4"), secs=2674, still=1200,
         poster=commons("c/c1/Sherlock_jr_poster.jpg"), director="Buster Keaton",
         plot="A cinema projectionist who dreams of being a detective falls asleep and walks straight into the film on screen.",
         licence="Public domain"),
    dict(id=203, cat="2", title="Safety Last!", year=1923, genre="Comedy, Romance", rating=8.1,
         src=ia("silent-safety-last", "Safety Last!.mp4"), secs=4433, still=3600,
         poster=commons("5/5e/Safety_last_poster.jpg"), director="Fred C. Newmeyer, Sam Taylor",
         plot="To impress his sweetheart, a shop clerk agrees to climb the outside of a twelve-storey building.",
         licence="Public domain"),
    dict(id=204, cat="2", title="Steamboat Bill, Jr.", year=1928, genre="Comedy, Action", rating=7.9,
         src=ia("steamboat_bill_ipod", "steamboat_bill.mp4"), secs=4148, still=3300,
         poster=commons("c/cf/Steamboat_bill_poster.jpg"), director="Charles Reisner",
         plot="A college boy returns to his gruff riverboat father just as a cyclone hits the town.",
         licence="Public domain"),
    dict(id=205, cat="2", title="The Cabinet of Dr. Caligari", year=1920, genre="Horror, Mystery", rating=8.0,
         src=ia("DasKabinettdesDoktorCaligariTheCabinetofDrCaligari", "The_Cabinet_of_Dr._Caligari_512kb.mp4"), secs=3061, still=900,
         poster=commons("5/52/Das_Cabinet_des_Dr._Caligari.JPG"), director="Robert Wiene",
         plot="A fairground hypnotist and his sleepwalker arrive in a small town, and the murders begin.",
         licence="Public domain"),
    dict(id=206, cat="2", title="A Trip to the Moon", year=1902, genre="Sci-Fi, Adventure", rating=8.1,
         src=ia("le-voyage-dans-la-lune-1902-georges-melies", "Le Voyage Dans La Lune - (1902) - Georges Méliès.ia.mp4"), secs=932, still=300,
         poster=commons("2/2b/Voyage_dans_la_lune_title_card.png"), director="Georges Méliès",
         plot="Six astronomers fire themselves at the Moon in a giant shell and meet its strange inhabitants.",
         licence="Public domain"),
    dict(id=207, cat="2", title="Sunrise", year=1927, genre="Drama, Romance", rating=8.1,
         src=ia("sunrise-1927_202301", "Sunrise.ia.mp4"), secs=5697, still=2400,
         poster=commons("2/27/Sunrise_-_A_Song_of_Two_Humans.jpg"), director="F. W. Murnau",
         plot="A farmer tempted by a woman from the city takes his wife across the lake, and the day changes them both.",
         licence="Public domain"),
    dict(id=208, cat="2", title="The Lost World", year=1925, genre="Adventure, Sci-Fi", rating=6.6,
         src=ia("lost_world", "lost_world.mp4"), secs=4085, still=1900,
         poster=commons("7/76/The_Lost_World_%281925%29_-_film_poster.jpg"), director="Harry O. Hoyt",
         plot="An expedition into the Amazon finds a high plateau where dinosaurs still roam.",
         licence="Public domain"),
    dict(id=301, cat="3", title="Detour", year=1945, genre="Crime, Drama", rating=7.2,
         src=ia("Detour", "Detour.mp4"), secs=4058, still=2600,
         poster=commons("4/47/Detour_%28poster%29.jpg"), director="Edgar G. Ulmer",
         plot="A nightclub pianist hitchhiking to Los Angeles is pulled into one bad turn after another.",
         licence="Public domain"),
    dict(id=302, cat="3", title="Carnival of Souls", year=1962, genre="Horror, Mystery", rating=7.0,
         src=ia("CarnivalofSouls", "CarnivalOfSouls.mp4"), secs=4980, still=1300,
         poster=commons("b/bd/Carnival_of_Souls_%281962_pressbook_cover%29.jpg"), director="Herk Harvey",
         plot="After surviving a car crash, a church organist is drawn to an abandoned lakeside pavilion.",
         licence="Public domain"),
    dict(id=303, cat="3", title="House on Haunted Hill", year=1959, genre="Horror, Mystery", rating=6.8,
         src=ia("The_House_On_Haunted_Hill", "The_House_On_Haunted_Hill.mp4"), secs=4483, still=700,
         poster=commons("2/24/House_on_Haunted_Hill.jpg"), director="William Castle",
         plot="A millionaire offers five guests a fortune if they survive one night locked in a haunted house.",
         licence="Public domain"),
    dict(id=304, cat="3", title="The Little Shop of Horrors", year=1960, genre="Comedy, Horror", rating=6.1,
         src=ia("The_Little_Shop_of_Horrors_60", "The_Little_Shop_of_Horrors_60.mp4"), secs=4385, still=900,
         poster=commons("1/1c/The_Little_Shop_of_Horrors_%281960%29_-_Half-Sheet_poster.webp"), director="Roger Corman",
         plot="A clumsy flower shop assistant raises a strange plant that only grows on one thing.",
         licence="Public domain"),
    dict(id=305, cat="3", title="Plan 9 from Outer Space", year=1957, genre="Sci-Fi, Horror", rating=4.0,
         src=ia("plan-9-from-outer-space", "plan-9-from-outer-space.mp4"), secs=4700, still=1700,
         poster=commons("b/bf/Plan_9_Alternative_poster.jpg"), director="Ed Wood",
         plot="Visitors from space raise the dead of a small Californian town to stop humanity's deadliest weapon.",
         licence="Public domain"),
    dict(id=401, cat="4", title="His Girl Friday", year=1940, genre="Comedy, Romance", rating=7.8,
         src=ia("his_girl_friday", "his_girl_friday.mp4"), secs=5505, still=1000,
         poster=commons("2/21/His_Girl_Friday_%281940_poster%29_crop.jpg"), director="Howard Hawks",
         plot="A newspaper editor uses one last big story to stop his star reporter, and former wife, from remarrying.",
         licence="Public domain"),
    dict(id=402, cat="4", title="Charade", year=1963, genre="Comedy, Mystery", rating=7.8,
         src=ia("charade-1963-cary-grant-audrey-hepburn-comedy-mystery-romance-thriller-full-movie", "Charade_READY.mp4"), secs=6785, still=1900,
         poster=commons("f/fd/Charade_%281963_poster%29.jpg"), director="Stanley Donen",
         plot="In Paris, a woman whose husband has just been murdered is chased by men who want his missing fortune.",
         licence="Public domain"),
]

SERIES_CATEGORIES = [("11", "Animation"), ("12", "Silent Comedy")]

SERIES = [
    dict(id=501, cat="11", title="Caminandes", year=2013, genre="Animation, Comedy", rating=7.4,
         poster=commons("6/61/Pablo_Vazquez_-_Caminandes_-_Episode_1_-_Llama_Drama_-_Cover_thumbnail.png"),
         director="Pablo Vazquez",
         plot="Koro the llama tries everything to reach the greener grass on the other side, in Patagonia's wide open spaces.",
         licence="CC BY 3.0, Blender Foundation",
         episodes=[
             dict(id=5011, title="Llama Drama", src=ia("Caminandes1LlamaDrama", "01_llama_drama_1080p.mp4"), secs=90, still=40,
                  plot="Koro meets a road that won't let him cross."),
             dict(id=5012, title="Gran Dillama", src=ia("Caminandes2GranDillama", "02_gran_dillama_1080p.mp4"), secs=146, still=60,
                  plot="A fence stands between Koro and the juiciest grass in the valley."),
             dict(id=5013, title="Llamigos", src=ia("CaminandesLlamigos", "Caminandes_ Llamigos-1080p.mp4"), secs=150, still=70,
                  plot="Winter comes, and a penguin has its eye on the last berries."),
         ]),
    dict(id=502, cat="12", title="Two-Reel Comedies", year=1920, genre="Comedy", rating=7.9,
         poster=commons("d/d8/Buster_Keaton_One_Week_Ad_-_Motion_Picture_News_%28Oct_9%2C_1920%29.jpg"),
         director="Buster Keaton, Edward F. Cline",
         plot="Short silent comedies from 1920 to 1922, full of daring stunts and impossible houses.",
         licence="Public domain",
         episodes=[
             dict(id=5021, title="One Week", src=ia("OneWeek", "One_Week_512kb.mp4"), secs=1337, still=500,
                  plot="Newlyweds build a flat-pack house, but someone has swapped the numbers on the boxes."),
             dict(id=5022, title="The Scarecrow", src=ia("TheScarecrow1920", "The-Scarecrow-v2.mp4"), secs=1086, still=420,
                  plot="Two farmhands share a house full of clever gadgets, and both want the same girl."),
             dict(id=5023, title="Neighbors", src=ia("silent-neighbors", "Neighbors.mp4"), secs=1064, still=380,
                  plot="Young lovers in neighbouring tenements fight their feuding families across the fence."),
             dict(id=5024, title="The Haunted House", src=ia("TheHauntedHouse", "TheHauntedHouse.mp4"), secs=1237, still=600,
                  plot="A bank clerk hides from robbers in a house rigged to scare visitors away."),
             dict(id=5025, title="The Goat", src=ia("silent-the-goat", "The Goat.mp4"), secs=1408, still=700,
                  plot="Mistaken for an escaped criminal, a man runs from the whole police force."),
             dict(id=5026, title="Cops", src=ia("cops-busterkeaton", "cops.mp4"), secs=945, still=520,
                  plot="Trying to prove himself, a young man drives a horse and cart straight into a police parade."),
         ]),
]

LIVE_CATEGORIES = [("21", "Movies"), ("22", "Classics"), ("23", "Kids & Animation"), ("24", "Science & Space"), ("25", "Test Streams")]

# Channels play a film or a public stream on a loop; the guide below shows that film in slots.
APPLE_BIPBOP = "https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_16x9/bipbop_16x9_variant.m3u8"
CHANNELS = [
    dict(id=1, cat="21", name="Open Movie Channel", src="https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8", films=[101, 102, 104, 105, 106, 103]),
    dict(id=2, cat="21", name="Science Fiction", src="https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8", films=[103, 206, 208, 305]),
    dict(id=3, cat="21", name="Mystery Movies", src=MOVIES[14]["src"], films=[301, 302, 303, 304]),
    dict(id=4, cat="21", name="Screwball", src=MOVIES[19]["src"], films=[401, 402]),
    dict(id=5, cat="22", name="Silent Cinema", src=MOVIES[6]["src"], films=[201, 202, 203, 204]),
    dict(id=6, cat="22", name="Early Film", src=MOVIES[11]["src"], films=[206, 205, 207]),
    dict(id=7, cat="22", name="Comedy Shorts", src=SERIES[1]["episodes"][0]["src"], episodes=502),
    dict(id=8, cat="23", name="Llama TV", src=SERIES[0]["episodes"][2]["src"], episodes=501),
    dict(id=9, cat="23", name="Animation Station", src=MOVIES[0]["src"], films=[101, 106, 105, 104]),
    dict(id=10, cat="24", name="Space Live", src="https://ntv1.akamaized.net/hls/live/2014075/NASA-NTV1-HLS/master.m3u8",
         shows=["Space Station Live", "Mission Briefing", "Earth from Orbit", "Launch Replay", "Science Hour"]),
    dict(id=11, cat="24", name="Apollo Archive", src=ia("Apollo1116mmOnboardFilm", "apollo11_6_1.mp4"),
         shows=["Apollo 11: Onboard Film", "Moonwalk Highlights", "Mission Control", "Return to Earth"]),
    dict(id=12, cat="25", name="Live Test Clock", src="https://demo.unified-streaming.com/k8s/live/stable/live.isml/.m3u8",
         shows=["Live Test Signal"]),
    dict(id=13, cat="25", name="Test Pattern HD", src=APPLE_BIPBOP, shows=["Test Pattern"]),
    dict(id=14, cat="25", name="Low Latency Test", src="https://cph-p2p-msl.akamaized.net/hls/live/2000341/test/master.m3u8",
         shows=["Low Latency Test"]),
]


def img(name):
    return f"{SITE}/img/{name}"


def movie_json(m):
    return {
        "num": m["id"], "name": f'{m["title"]} ({m["year"]})', "stream_type": "movie", "stream_id": m["id"],
        "stream_icon": img(f'm{m["id"]}.jpg'), "rating": m["rating"], "category_id": m["cat"],
        "container_extension": "mp4", "added": "1767225600", "direct_source": m["src"],
    }


def movie_info(m):
    mins = m["secs"] // 60
    return {
        "info": {
            "name": m["title"], "plot": m["plot"], "genre": m["genre"], "director": m["director"],
            "releasedate": f'{m["year"]}-01-01', "duration_secs": m["secs"],
            "duration": f"{mins // 60:02d}:{mins % 60:02d}:00",
            "backdrop_path": [img(f'm{m["id"]}-still.jpg')], "rating": m["rating"], "age": "",
        },
        "movie_data": {"stream_id": m["id"], "name": m["title"], "container_extension": "mp4",
                       "category_id": m["cat"], "direct_source": m["src"]},
    }


def series_json(s):
    return {
        "num": s["id"], "name": s["title"], "series_id": s["id"], "cover": img(f's{s["id"]}.jpg'),
        "plot": s["plot"], "genre": s["genre"], "releaseDate": f'{s["year"]}-01-01', "rating": s["rating"],
        "backdrop_path": [img(f's{s["id"]}-still.jpg')], "category_id": s["cat"], "director": s["director"],
    }


def series_info(s):
    eps = []
    for n, e in enumerate(s["episodes"], 1):
        eps.append({
            "id": str(e["id"]), "episode_num": n, "title": e["title"], "season": 1, "container_extension": "mp4",
            "direct_source": e["src"],
            "info": {"duration_secs": e["secs"], "movie_image": img(f'e{e["id"]}.jpg'), "plot": e["plot"]},
        })
    return {
        "seasons": [{"season_number": 1, "name": "Season 1", "episode_count": len(eps)}],
        "info": {"name": s["title"], "plot": s["plot"], "genre": s["genre"], "director": s["director"],
                 "cover": img(f's{s["id"]}.jpg'), "backdrop_path": [img(f's{s["id"]}-still.jpg')]},
        "episodes": {"1": eps},
    }


def write_json(path, data):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def build_json():
    write_json("player_api/account.json", {
        "user_info": {"username": "demo", "auth": 1, "status": "Active", "exp_date": None,
                      "max_connections": "1", "allowed_output_formats": ["m3u8"]},
        "server_info": {"url": "lumen-tv.github.io", "server_protocol": "https", "timezone": "UTC"},
    })
    cats = lambda pairs: [{"category_id": i, "category_name": n, "parent_id": 0} for i, n in pairs]
    write_json("player_api/get_live_categories.json", cats(LIVE_CATEGORIES))
    write_json("player_api/get_vod_categories.json", cats(MOVIE_CATEGORIES))
    write_json("player_api/get_series_categories.json", cats(SERIES_CATEGORIES))
    write_json("player_api/get_live_streams.json", [
        {"num": c["id"], "name": c["name"], "stream_type": "live", "stream_id": c["id"], "stream_icon": "",
         "epg_channel_id": f'demo{c["id"]}', "category_id": c["cat"], "tv_archive": 0, "direct_source": c["src"]}
        for c in CHANNELS
    ])
    write_json("player_api/get_vod_streams.json", [movie_json(m) for m in MOVIES])
    write_json("player_api/get_series.json", [series_json(s) for s in SERIES])
    for m in MOVIES:
        write_json(f'player_api/get_vod_info-{m["id"]}.json', movie_info(m))
    for s in SERIES:
        write_json(f'player_api/get_series_info-{s["id"]}.json', series_info(s))


# MARK: guide

def build_guide(days=21):
    movies = {m["id"]: m for m in MOVIES}
    series = {s["id"]: s for s in SERIES}
    start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=1)
    end = start + dt.timedelta(days=days + 1)
    fmt = lambda t: t.strftime("%Y%m%d%H%M%S +0000")
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="Lumen demo">']
    for c in CHANNELS:
        out.append(f'<channel id="demo{c["id"]}"><display-name>{escape(c["name"])}</display-name></channel>')
    for c in CHANNELS:
        if "films" in c:
            items = [(movies[i]["title"], movies[i]["plot"], movies[i]["genre"], movies[i]["secs"]) for i in c["films"]]
        elif "episodes" in c:
            s = series[c["episodes"]]
            items = [(f'{s["title"]}: {e["title"]}', e["plot"], s["genre"], e["secs"]) for e in s["episodes"]]
        else:
            items = [(t, "", "Science" if c["cat"] == "24" else "Test", 3600) for t in c["shows"]]
        t, n = start, 0
        while t < end:
            title, plot, genre, secs = items[n % len(items)]
            # Slots run to the next quarter hour, so the grid lines up like a real channel's.
            length = max(15, -(-(secs // 60) // 15) * 15)
            stop = t + dt.timedelta(minutes=length)
            desc = f"<desc>{escape(plot)}</desc>" if plot else ""
            out.append(f'<programme start="{fmt(t)}" stop="{fmt(stop)}" channel="demo{c["id"]}">'
                       f'<title>{escape(title)}</title>{desc}<category>{escape(genre)}</category></programme>')
            t, n = stop, n + 1
    out.append("</tv>")
    with open(os.path.join(OUT, "xmltv.xml"), "w") as f:
        f.write("\n".join(out) + "\n")


# MARK: images

def fetch(url, path):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())


def thumb(url, width=500):
    """Commons asks bots for its standard thumbnail sizes, not originals."""
    path = url.split("/wikipedia/commons/", 1)[1]
    file = path.rsplit("/", 1)[1]
    ext = ".png" if file.lower().endswith(".webp") else ""
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{path}/{width}px-{file}{ext}"


def poster(url, name, width=500):
    from PIL import Image
    raw = os.path.join("/tmp", "lumen-demo-" + hashlib.sha1(url.encode()).hexdigest())
    if not os.path.exists(raw):
        time.sleep(20)  # Commons rate-limits quick bursts
        fetch(thumb(url) if "/wikipedia/commons/" in url else url, raw)
    im = Image.open(raw).convert("RGB")
    h = round(im.height * width / im.width)
    im.resize((width, h), Image.LANCZOS).save(os.path.join(OUT, "img", name), quality=82, optimize=True)


def still(src, at, name, width=1280):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at), "-i", src, "-frames:v", "1",
                    "-vf", f"scale={width}:-2", "-q:v", "4", os.path.join(OUT, "img", name)], check=True, timeout=120)


def build_images():
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    jobs = [(poster, m["poster"], f'm{m["id"]}.jpg') for m in MOVIES]
    jobs += [(still, m["src"], m["still"], f'm{m["id"]}-still.jpg') for m in MOVIES]
    for s in SERIES:
        jobs.append((poster, s["poster"], f's{s["id"]}.jpg'))
        e = s["episodes"][0]
        jobs.append((still, e["src"], e["still"], f's{s["id"]}-still.jpg'))
        jobs += [(still, e["src"], e["still"], f'e{e["id"]}.jpg', 640) for e in s["episodes"]]
    for fn, *args in jobs:
        name = args[1] if fn is poster else args[2]
        if os.path.exists(os.path.join(OUT, "img", name)):
            continue
        try:
            fn(*args)
            print("ok", name)
        except Exception as e:  # keep going; the summary lists what's missing
            print("FAILED", name, e, file=sys.stderr)


def build_credits():
    lines = ["# Lumen demo library: sources", "",
             "Everything here is free to show and play. Videos are linked, not copied.", ""]
    for m in MOVIES:
        lines.append(f'- **{m["title"]}** ({m["year"]}), {m["licence"]}. Video: {m["src"]} · Poster: {m["poster"]}')
    for s in SERIES:
        lines.append(f'- **{s["title"]}**, {s["licence"]}. Poster: {s["poster"]}')
        for e in s["episodes"]:
            lines.append(f'  - {e["title"]}: {e["src"]}')
    lines += ["", "Live channels loop the films above, public-domain NASA footage and public HLS test streams:", ""]
    lines += [f'- {c["name"]}: {c["src"]}' for c in CHANNELS]
    with open(os.path.join(OUT, "CREDITS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build_json()
    build_guide()
    build_credits()
    if "--images" in sys.argv:
        build_images()
