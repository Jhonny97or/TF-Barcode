import os
import math
import time
import requests

from collections import Counter, defaultdict
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from flask import Flask, request, Response, jsonify


# ============================================================
# FLASK / VERCEL ENTRYPOINT
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

API_KEY = (
    os.getenv("MASSIVE_API_KEY")
    or os.getenv("POLYGON_API_KEY")
)

LOGIN_USER = os.getenv("LOGIN_USER")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD")

BASE_URL = "https://api.massive.com"

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


# ============================================================
# CONFIGURACIÓN DEL SCANNER
# ============================================================

MIN_PRICE = 1.00
MAX_PRICE = 5.00

# Volumen mínimo actual
MIN_DAY_VOLUME = 250_000

# Número máximo de acciones que analizamos en profundidad
MAX_CANDIDATES = 90

# Top final
TOP_RESULTS = 30

# Mínimo de barras/minutos de negociación por sesión
MIN_ACTIVE_MINUTES = 60

# Paralelismo
MAX_WORKERS = 10

# Timeout por request
REQUEST_TIMEOUT = 12

# Cache
CACHE_SECONDS = 60


# ============================================================
# SESIÓN HTTP
# ============================================================

session = requests.Session()


# ============================================================
# CACHE
# ============================================================

CACHE = {
    "timestamp": 0,
    "data": None
}


# ============================================================
# HELPERS
# ============================================================

def clean_number(value, default=0.0):

    try:

        if value is None:
            return default

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except Exception:
        return default


def safe_div(a, b, default=0.0):

    try:

        b = float(b)

        if b == 0:
            return default

        return float(a) / b

    except Exception:
        return default


def clamp(
    value,
    minimum=0.0,
    maximum=100.0
):

    return max(
        minimum,
        min(
            maximum,
            value
        )
    )


# ============================================================
# AUTENTICACIÓN
# ============================================================

def valid_login():

    # Si no existen credenciales en Vercel,
    # NO permitimos acceso.
    if not LOGIN_USER or not LOGIN_PASSWORD:
        return False

    auth = request.authorization

    if auth is None:
        return False

    return (
        auth.username == LOGIN_USER
        and
        auth.password == LOGIN_PASSWORD
    )


def authentication_required():

    return Response(
        "Authentication required.",
        status=401,
        headers={
            "WWW-Authenticate":
                'Basic realm="TF Barcode Scanner"',
            "Cache-Control":
                "no-store"
        },
        mimetype="text/plain"
    )


@app.before_request
def protect_site():

    if not valid_login():
        return authentication_required()


# ============================================================
# REQUEST A MASSIVE / POLYGON
# ============================================================

def request_json(
    url,
    params=None
):

    if not API_KEY:

        raise RuntimeError(
            "MASSIVE_API_KEY no está configurada en Vercel."
        )

    params = dict(
        params or {}
    )

    params["apiKey"] = API_KEY

    try:

        response = session.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT
        )

        # ====================================================
        # FALLBACK POLYGON
        # ====================================================

        if (
            response.status_code != 200
            and
            "api.massive.com" in url
        ):

            fallback_url = url.replace(
                "api.massive.com",
                "api.polygon.io"
            )

            response = session.get(
                fallback_url,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

        response.raise_for_status()

        return response.json()

    except requests.HTTPError as exc:

        status = "?"
        text = ""

        try:

            status = exc.response.status_code
            text = exc.response.text[:300]

        except Exception:
            pass

        raise RuntimeError(
            f"API HTTP {status}: {text}"
        )

    except Exception as exc:

        raise RuntimeError(
            f"API request error: {str(exc)}"
        )


# ============================================================
# SNAPSHOT DE TODO EL MERCADO
# ============================================================

def get_market_snapshots():

    url = (
        f"{BASE_URL}"
        "/v2/snapshot/locale/"
        "us/markets/stocks/tickers"
    )

    data = request_json(
        url,
        {
            "include_otc": "false"
        }
    )

    tickers = (
        data.get(
            "tickers",
            []
        )
        or []
    )

    return tickers


# ============================================================
# PRECIO DEL SNAPSHOT
# ============================================================

def snapshot_price(item):

    last_trade = (
        item.get(
            "lastTrade",
            {}
        )
        or {}
    )

    day = (
        item.get(
            "day",
            {}
        )
        or {}
    )

    prev_day = (
        item.get(
            "prevDay",
            {}
        )
        or {}
    )

    return clean_number(

        last_trade.get("p")
        or day.get("c")
        or prev_day.get("c")
        or 0

    )


# ============================================================
# VOLUMEN DEL SNAPSHOT
# ============================================================

def snapshot_volume(item):

    day = (
        item.get(
            "day",
            {}
        )
        or {}
    )

    prev_day = (
        item.get(
            "prevDay",
            {}
        )
        or {}
    )

    return clean_number(
        day.get("v")
        or prev_day.get("v")
        or 0
    )


# ============================================================
# OBTENER CANDIDATOS $1 - $5
# ============================================================

def get_candidates():

    snapshots = get_market_snapshots()

    candidates = []

    for item in snapshots:

        ticker = item.get(
            "ticker"
        )

        if not ticker:
            continue

        price = snapshot_price(
            item
        )

        volume = snapshot_volume(
            item
        )

        # ====================================================
        # PRECIO
        # ====================================================

        if price < MIN_PRICE:
            continue

        if price > MAX_PRICE:
            continue

        # ====================================================
        # VOLUMEN
        # ====================================================

        if volume < MIN_DAY_VOLUME:
            continue

        # ====================================================
        # EVITAR SÍMBOLOS EXTRAÑOS
        # ====================================================

        if len(ticker) > 6:
            continue

        candidates.append(
            {
                "ticker":
                    ticker,

                "price":
                    round(
                        price,
                        4
                    ),

                "day_volume":
                    int(
                        volume
                    )
            }
        )

    # ========================================================
    # MÁS LÍQUIDOS PRIMERO
    # ========================================================

    candidates.sort(
        key=lambda x: x[
            "day_volume"
        ],
        reverse=True
    )

    return candidates[
        :MAX_CANDIDATES
    ]


# ============================================================
# DESCARGAR BARRAS DE 1 MINUTO
# ============================================================

def get_minute_bars(
    ticker
):

    now = datetime.now(
        NY_TZ
    )

    # Buscamos 7 días calendario para capturar
    # cómodamente las últimas dos sesiones hábiles.
    start_date = (
        now.date()
        - timedelta(
            days=7
        )
    )

    end_date = now.date()

    url = (
        f"{BASE_URL}"
        f"/v2/aggs/ticker/"
        f"{ticker}"
        f"/range/1/minute/"
        f"{start_date.strftime('%Y-%m-%d')}"
        f"/{end_date.strftime('%Y-%m-%d')}"
    )

    data = request_json(
        url,
        {
            "adjusted":
                "true",

            "sort":
                "asc",

            "limit":
                50000
        }
    )

    results = (
        data.get(
            "results",
            []
        )
        or []
    )

    bars = []

    for bar in results:

        timestamp = bar.get(
            "t"
        )

        if timestamp is None:
            continue

        dt = datetime.fromtimestamp(
            timestamp / 1000,
            tz=UTC_TZ
        ).astimezone(
            NY_TZ
        )

        # ====================================================
        # SOLO MERCADO REGULAR
        # 09:30 - 16:00 ET
        # ====================================================

        current_time = dt.time()

        if current_time < dt_time(
            9,
            30
        ):
            continue

        if current_time > dt_time(
            16,
            0
        ):
            continue

        bars.append(
            {
                "dt":
                    dt,

                "date":
                    dt.date(),

                "open":
                    clean_number(
                        bar.get("o")
                    ),

                "high":
                    clean_number(
                        bar.get("h")
                    ),

                "low":
                    clean_number(
                        bar.get("l")
                    ),

                "close":
                    clean_number(
                        bar.get("c")
                    ),

                "volume":
                    clean_number(
                        bar.get("v")
                    ),

                "transactions":
                    clean_number(
                        bar.get("n")
                    )
            }
        )

    return bars


# ============================================================
# AGRUPAR BARRAS POR SESIÓN
# ============================================================

def group_sessions(
    bars
):

    sessions = defaultdict(
        list
    )

    for bar in bars:

        sessions[
            bar["date"]
        ].append(
            bar
        )

    valid_sessions = []

    for date_value in sorted(
        sessions.keys()
    ):

        day_bars = sessions[
            date_value
        ]

        # Necesitamos un mínimo de actividad.
        if len(
            day_bars
        ) >= MIN_ACTIVE_MINUTES:

            valid_sessions.append(
                (
                    date_value,
                    day_bars
                )
            )

    return valid_sessions


# ============================================================
# ANALIZAR COMPORTAMIENTO "BARCODE" DE UN DÍA
# ============================================================

def analyze_barcode_day(
    bars
):

    if len(
        bars
    ) < MIN_ACTIVE_MINUTES:

        return None

    # ========================================================
    # CIERRES REDONDEADOS A CENTAVOS
    # ========================================================

    closes = [

        round(
            bar["close"],
            2
        )

        for bar in bars

        if bar[
            "close"
        ] > 0
    ]

    if len(
        closes
    ) < MIN_ACTIVE_MINUTES:

        return None


    highs = [

        bar["high"]

        for bar in bars

        if bar[
            "high"
        ] > 0
    ]


    lows = [

        bar["low"]

        for bar in bars

        if bar[
            "low"
        ] > 0
    ]


    if not highs or not lows:
        return None


    # ========================================================
    # 1. BARRAS PEQUEÑAS
    # ========================================================

    small_bars = 0
    one_cent_bars = 0
    zero_range_bars = 0


    for bar in bars:

        bar_range = (
            bar["high"]
            - bar["low"]
        )

        # Barra <= 2 centavos
        if bar_range <= 0.0201:
            small_bars += 1

        # Barra <= 1 centavo
        if bar_range <= 0.0101:
            one_cent_bars += 1

        # Prácticamente sin rango
        if bar_range <= 0.001:
            zero_range_bars += 1


    small_bar_pct = safe_div(
        small_bars,
        len(bars)
    ) * 100


    one_cent_bar_pct = safe_div(
        one_cent_bars,
        len(bars)
    ) * 100


    zero_range_pct = safe_div(
        zero_range_bars,
        len(bars)
    ) * 100


    # ========================================================
    # 2. CAMBIOS ENTRE MINUTOS
    # ========================================================

    tiny_steps = 0
    same_level = 0
    one_cent_steps = 0
    two_cent_steps = 0


    for i in range(
        1,
        len(closes)
    ):

        delta = abs(
            closes[i]
            - closes[i - 1]
        )

        # Cambio <= $0.02
        if delta <= 0.0201:
            tiny_steps += 1

        # Exactamente el mismo centavo
        if delta <= 0.001:
            same_level += 1

        # Aproximadamente 1 centavo
        if (
            delta >= 0.009
            and
            delta <= 0.011
        ):
            one_cent_steps += 1

        # Aproximadamente 2 centavos
        if (
            delta >= 0.019
            and
            delta <= 0.021
        ):
            two_cent_steps += 1


    transitions = max(
        1,
        len(closes)
        - 1
    )


    tiny_step_pct = (
        tiny_steps
        / transitions
        * 100
    )


    same_level_pct = (
        same_level
        / transitions
        * 100
    )


    one_cent_step_pct = (
        one_cent_steps
        / transitions
        * 100
    )


    two_cent_step_pct = (
        two_cent_steps
        / transitions
        * 100
    )


    # ========================================================
    # 3. REPETICIÓN DE NIVELES
    # ========================================================

    level_counts = Counter(
        closes
    )


    repeated_minutes = sum(

        count

        for count
        in level_counts.values()

        if count >= 3
    )


    repeated_level_pct = safe_div(
        repeated_minutes,
        len(closes)
    ) * 100


    unique_levels = len(
        level_counts
    )


    # ========================================================
    # CONCENTRACIÓN EN LOS NIVELES MÁS FRECUENTES
    # ========================================================

    most_common = level_counts.most_common(
        5
    )

    top5_level_minutes = sum(
        count
        for _, count
        in most_common
    )

    top5_level_pct = safe_div(
        top5_level_minutes,
        len(closes)
    ) * 100


    # ========================================================
    # 4. RANGO TOTAL DEL DÍA
    # ========================================================

    day_high = max(
        highs
    )

    day_low = min(
        lows
    )

    average_price = (
        sum(
            closes
        )
        / len(
            closes
        )
    )


    day_range_pct = safe_div(
        (
            day_high
            - day_low
        ),
        average_price
    ) * 100


    # ========================================================
    # SCORE DEL RANGO
    # ========================================================

    if day_range_pct <= 3:

        range_score = 100

    elif day_range_pct <= 5:

        range_score = 92

    elif day_range_pct <= 8:

        range_score = 80

    elif day_range_pct <= 12:

        range_score = 60

    elif day_range_pct <= 18:

        range_score = 35

    elif day_range_pct <= 25:

        range_score = 15

    else:

        range_score = 5


    # ========================================================
    # 5. ACTIVIDAD
    # ========================================================

    active_minutes = len(
        bars
    )


    activity_score = clamp(

        safe_div(
            active_minutes,
            300
        )
        * 100

    )


    # ========================================================
    # 6. PENALIZAR EXCESO DE NIVELES DIFERENTES
    # ========================================================

    unique_level_ratio = safe_div(
        unique_levels,
        len(closes)
    )


    # Un barcode normalmente reutiliza muchos precios.
    if unique_level_ratio <= 0.10:

        level_efficiency_score = 100

    elif unique_level_ratio <= 0.15:

        level_efficiency_score = 90

    elif unique_level_ratio <= 0.20:

        level_efficiency_score = 80

    elif unique_level_ratio <= 0.30:

        level_efficiency_score = 60

    elif unique_level_ratio <= 0.40:

        level_efficiency_score = 40

    else:

        level_efficiency_score = 20


    # ========================================================
    # 7. SCORE FINAL DEL DÍA
    # ========================================================

    compression_score = clamp(
        small_bar_pct
    )

    step_score = clamp(
        tiny_step_pct
    )

    repetition_score = clamp(
        repeated_level_pct
    )


    final_score = (

        # Muchos candles de 1m pequeños
        compression_score
        * 0.25

        +

        # Minuto a minuto cambia poco
        step_score
        * 0.22

        +

        # Reutiliza precios
        repetition_score
        * 0.18

        +

        # Rango diario controlado
        range_score
        * 0.10

        +

        # Muchísimas barras <= 1 centavo
        one_cent_bar_pct
        * 0.07

        +

        # Cierres exactamente iguales
        same_level_pct
        * 0.06

        +

        # Concentración en pocos precios
        top5_level_pct
        * 0.04

        +

        # Cantidad eficiente de niveles
        level_efficiency_score
        * 0.04

        +

        # No queremos stocks completamente muertos
        activity_score
        * 0.04
    )


    # ========================================================
    # PENALIZACIONES
    # ========================================================

    # Si las barras pequeñas son pocas,
    # no debe considerarse barcode.
    if small_bar_pct < 45:

        final_score *= 0.72


    # Si los cambios minuto a minuto son demasiado grandes.
    if tiny_step_pct < 55:

        final_score *= 0.75


    # Si casi nunca repite precios.
    if repeated_level_pct < 40:

        final_score *= 0.80


    # ========================================================
    # RESULTADO
    # ========================================================

    return {

        "score":
            round(
                clamp(
                    final_score
                ),
                2
            ),

        "small_bar_pct":
            round(
                small_bar_pct,
                1
            ),

        "one_cent_bar_pct":
            round(
                one_cent_bar_pct,
                1
            ),

        "zero_range_pct":
            round(
                zero_range_pct,
                1
            ),

        "tiny_step_pct":
            round(
                tiny_step_pct,
                1
            ),

        "same_level_pct":
            round(
                same_level_pct,
                1
            ),

        "one_cent_step_pct":
            round(
                one_cent_step_pct,
                1
            ),

        "two_cent_step_pct":
            round(
                two_cent_step_pct,
                1
            ),

        "repeated_level_pct":
            round(
                repeated_level_pct,
                1
            ),

        "top5_level_pct":
            round(
                top5_level_pct,
                1
            ),

        "day_range_pct":
            round(
                day_range_pct,
                2
            ),

        "active_minutes":
            active_minutes,

        "unique_levels":
            unique_levels,

        "level_efficiency_score":
            round(
                level_efficiency_score,
                1
            ),

        "high":
            round(
                day_high,
                4
            ),

        "low":
            round(
                day_low,
                4
            )
    }


# ============================================================
# ANALIZAR UN TICKER COMPLETO
# ============================================================

def analyze_ticker(
    candidate
):

    ticker = candidate[
        "ticker"
    ]

    try:

        bars = get_minute_bars(
            ticker
        )

        sessions = group_sessions(
            bars
        )

        # ====================================================
        # DEBE TENER DOS SESIONES VÁLIDAS
        # ====================================================

        if len(
            sessions
        ) < 2:

            return None


        # ====================================================
        # ÚLTIMAS DOS SESIONES
        # ====================================================

        last_two = sessions[
            -2:
        ]


        date1, bars1 = (
            last_two[0]
        )

        date2, bars2 = (
            last_two[1]
        )


        day1 = analyze_barcode_day(
            bars1
        )

        day2 = analyze_barcode_day(
            bars2
        )


        if (
            day1 is None
            or
            day2 is None
        ):

            return None


        score1 = day1[
            "score"
        ]

        score2 = day2[
            "score"
        ]


        # ====================================================
        # CONSISTENCIA ENTRE AMBOS DÍAS
        # ====================================================

        difference = abs(
            score1
            - score2
        )


        consistency_score = clamp(
            100
            - (
                difference
                * 3
            )
        )


        weakest_day = min(
            score1,
            score2
        )


        # ====================================================
        # SCORE GENERAL
        # ====================================================

        two_day_score = (

            score1
            * 0.45

            +

            score2
            * 0.45

            +

            consistency_score
            * 0.10
        )


        # ====================================================
        # REGLA IMPORTANTE:
        # AMBOS DÍAS DEBEN SER BUENOS
        # ====================================================

        if weakest_day < 35:

            two_day_score *= 0.45

        elif weakest_day < 45:

            two_day_score *= 0.65

        elif weakest_day < 55:

            two_day_score *= 0.82


        # ====================================================
        # BONUS SI AMBOS DÍAS SON MUY "BARCODE"
        # ====================================================

        if (
            day1[
                "small_bar_pct"
            ] >= 75
            and
            day2[
                "small_bar_pct"
            ] >= 75
            and
            day1[
                "tiny_step_pct"
            ] >= 80
            and
            day2[
                "tiny_step_pct"
            ] >= 80
        ):

            two_day_score += 3


        two_day_score = clamp(
            two_day_score
        )


        # ====================================================
        # CLASIFICACIÓN
        # ====================================================

        if two_day_score >= 85:

            quality = (
                "EXTREME"
            )

        elif two_day_score >= 75:

            quality = (
                "VERY HIGH"
            )

        elif two_day_score >= 65:

            quality = (
                "HIGH"
            )

        elif two_day_score >= 55:

            quality = (
                "GOOD"
            )

        elif two_day_score >= 45:

            quality = (
                "WATCH"
            )

        else:

            quality = (
                "LOW"
            )


        # ====================================================
        # RESULTADO
        # ====================================================

        return {

            "ticker":
                ticker,

            "price":
                candidate[
                    "price"
                ],

            "day_volume":
                candidate[
                    "day_volume"
                ],

            "barcode_score":
                round(
                    two_day_score,
                    2
                ),

            "quality":
                quality,

            "consistency_score":
                round(
                    consistency_score,
                    2
                ),

            "weakest_day":
                round(
                    weakest_day,
                    2
                ),


            # =================================================
            # DÍA 1
            # =================================================

            "day1_date":
                str(
                    date1
                ),

            "day1_score":
                score1,

            "day1_small_bars":
                day1[
                    "small_bar_pct"
                ],

            "day1_one_cent_bars":
                day1[
                    "one_cent_bar_pct"
                ],

            "day1_tiny_steps":
                day1[
                    "tiny_step_pct"
                ],

            "day1_same_level":
                day1[
                    "same_level_pct"
                ],

            "day1_repetition":
                day1[
                    "repeated_level_pct"
                ],

            "day1_top5_levels":
                day1[
                    "top5_level_pct"
                ],

            "day1_range":
                day1[
                    "day_range_pct"
                ],

            "day1_minutes":
                day1[
                    "active_minutes"
                ],

            "day1_unique_levels":
                day1[
                    "unique_levels"
                ],


            # =================================================
            # DÍA 2
            # =================================================

            "day2_date":
                str(
                    date2
                ),

            "day2_score":
                score2,

            "day2_small_bars":
                day2[
                    "small_bar_pct"
                ],

            "day2_one_cent_bars":
                day2[
                    "one_cent_bar_pct"
                ],

            "day2_tiny_steps":
                day2[
                    "tiny_step_pct"
                ],

            "day2_same_level":
                day2[
                    "same_level_pct"
                ],

            "day2_repetition":
                day2[
                    "repeated_level_pct"
                ],

            "day2_top5_levels":
                day2[
                    "top5_level_pct"
                ],

            "day2_range":
                day2[
                    "day_range_pct"
                ],

            "day2_minutes":
                day2[
                    "active_minutes"
                ],

            "day2_unique_levels":
                day2[
                    "unique_levels"
                ]
        }

    except Exception as exc:

        return {

            "ticker":
                ticker,

            "error":
                str(
                    exc
                )
        }


# ============================================================
# CONSTRUIR RANKING
# ============================================================

def build_ranking():

    # ========================================================
    # CACHE
    # ========================================================

    now_ts = time.time()

    if (
        CACHE[
            "data"
        ] is not None
        and
        (
            now_ts
            - CACHE[
                "timestamp"
            ]
        ) < CACHE_SECONDS
    ):

        return CACHE[
            "data"
        ]


    started = time.time()


    # ========================================================
    # CANDIDATOS
    # ========================================================

    candidates = get_candidates()


    results = []

    errors = []


    # ========================================================
    # ANALIZAR EN PARALELO
    # ========================================================

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {

            executor.submit(
                analyze_ticker,
                candidate
            ):
            candidate

            for candidate
            in candidates
        }


        for future in as_completed(
            futures
        ):

            candidate = futures[
                future
            ]

            try:

                result = future.result()

                if not result:
                    continue


                if result.get(
                    "error"
                ):

                    errors.append(
                        (
                            candidate[
                                "ticker"
                            ]
                            +
                            ": "
                            +
                            result[
                                "error"
                            ]
                        )
                    )

                    continue


                results.append(
                    result
                )

            except Exception as exc:

                errors.append(
                    (
                        candidate[
                            "ticker"
                        ]
                        +
                        ": "
                        +
                        str(
                            exc
                        )
                    )
                )


    # ========================================================
    # ORDENAR POR MEJOR BARCODE
    # ========================================================

    results.sort(

        key=lambda x: (

            x[
                "barcode_score"
            ],

            x[
                "weakest_day"
            ],

            x[
                "consistency_score"
            ],

            x[
                "day_volume"
            ]

        ),

        reverse=True
    )


    # ========================================================
    # TOP 30
    # ========================================================

    results = results[
        :TOP_RESULTS
    ]


    # ========================================================
    # RANK
    # ========================================================

    for index, row in enumerate(
        results,
        start=1
    ):

        row[
            "rank"
        ] = index


    # ========================================================
    # RESPUESTA FINAL
    # ========================================================

    now = datetime.now(
        NY_TZ
    )


    output = {

        "scanner":
            "TF-Barcode",

        "price_min":
            MIN_PRICE,

        "price_max":
            MAX_PRICE,

        "min_volume":
            MIN_DAY_VOLUME,

        "candidates_analyzed":
            len(
                candidates
            ),

        "results_found":
            len(
                results
            ),

        "updated_at":
            now.strftime(
                "%Y-%m-%d %H:%M:%S ET"
            ),

        "execution_seconds":
            round(
                time.time()
                - started,
                2
            ),

        "ranking":
            results,

        "errors":
            errors[
                :10
            ]
    }


    # ========================================================
    # GUARDAR CACHE
    # ========================================================

    CACHE[
        "timestamp"
    ] = time.time()

    CACHE[
        "data"
    ] = output


    return output


# ============================================================
# LEER INDEX.HTML
# ============================================================

def load_frontend():

    current_file = (
        Path(__file__)
        .resolve()
    )

    project_root = (
        current_file
        .parent
        .parent
    )

    html_path = (
        project_root
        /
        "index.html"
    )

    if not html_path.exists():

        raise FileNotFoundError(
            (
                "No encontré index.html en: "
                +
                str(
                    html_path
                )
            )
        )

    return html_path.read_text(
        encoding="utf-8"
    )


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def home():

    try:

        html = load_frontend()

        return Response(
            html,
            status=200,
            mimetype="text/html",
            headers={
                "Cache-Control":
                    "no-store, no-cache, must-revalidate"
            }
        )

    except Exception as exc:

        return Response(
            (
                "Frontend loading error: "
                +
                str(
                    exc
                )
            ),
            status=500,
            mimetype="text/plain"
        )


# ============================================================
# API DEL RANKING
# ============================================================

@app.route("/api")
@app.route("/api/")
@app.route("/api/ranking")
@app.route("/api/ranking/")
def ranking():

    try:

        result = build_ranking()

        response = jsonify(
            result
        )

        response.headers[
            "Cache-Control"
        ] = (
            "no-store, max-age=0"
        )

        return response

    except Exception as exc:

        response = jsonify(
            {
                "error":
                    str(
                        exc
                    )
            }
        )

        response.status_code = 500

        response.headers[
            "Cache-Control"
        ] = "no-store"

        return response


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify(
        {
            "status":
                "ok",

            "scanner":
                "TF-Barcode",

            "api_key_configured":
                bool(
                    API_KEY
                ),

            "login_configured":
                bool(
                    LOGIN_USER
                    and
                    LOGIN_PASSWORD
                )
        }
    )
