<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
TF Barcode Scanner
</title>


<style>

* {
    box-sizing: border-box;
}


body {

    margin: 0;

    background:
        #070b11;

    color:
        #ffffff;

    font-family:
        Arial,
        Helvetica,
        sans-serif;

}


.container {

    width:
        min(
            1600px,
            96%
        );

    margin:
        25px auto 60px auto;

}


.header {

    display:
        flex;

    justify-content:
        space-between;

    align-items:
        center;

    gap:
        20px;

    margin-bottom:
        22px;

}


.title-area h1 {

    margin:
        0;

    font-size:
        26px;

    letter-spacing:
        0.5px;

}


.title-area p {

    margin:
        7px 0 0 0;

    color:
        #8f9dad;

    font-size:
        13px;

}


.live-box {

    text-align:
        right;

}


.status {

    display:
        inline-block;

    padding:
        7px 12px;

    border:
        1px solid #273545;

    border-radius:
        8px;

    background:
        #0c131c;

    font-size:
        12px;

    font-weight:
        700;

}


.updated {

    margin-top:
        7px;

    font-size:
        11px;

    color:
        #778698;

}


.summary {

    display:
        grid;

    grid-template-columns:
        repeat(
            4,
            minmax(
                150px,
                1fr
            )
        );

    gap:
        10px;

    margin-bottom:
        18px;

}


.card {

    background:
        #0c121a;

    border:
        1px solid #1e2a37;

    border-radius:
        10px;

    padding:
        14px 15px;

}


.card-label {

    color:
        #77889b;

    font-size:
        11px;

    text-transform:
        uppercase;

    letter-spacing:
        0.7px;

}


.card-value {

    margin-top:
        5px;

    font-size:
        18px;

    font-weight:
        700;

}


.table-wrapper {

    overflow-x:
        auto;

    border:
        1px solid #1d2936;

    border-radius:
        12px;

    background:
        #080d13;

}


table {

    width:
        100%;

    min-width:
        1250px;

    border-collapse:
        collapse;

}


thead {

    background:
        #0e151e;

}


th {

    padding:
        12px 10px;

    border-bottom:
        1px solid #253443;

    color:
        #8798aa;

    font-size:
        10px;

    text-align:
        right;

    text-transform:
        uppercase;

    letter-spacing:
        0.5px;

    white-space:
        nowrap;

}


th:nth-child(1),
th:nth-child(2),
th:nth-child(5) {

    text-align:
        left;

}


td {

    padding:
        12px 10px;

    border-bottom:
        1px solid #15212d;

    text-align:
        right;

    font-size:
        12px;

    white-space:
        nowrap;

}


tbody tr:hover {

    background:
        #0e1721;

}


.rank {

    text-align:
        left;

    font-size:
        15px;

    font-weight:
        800;

    width:
        50px;

}


.ticker {

    text-align:
        left;

    font-size:
        17px;

    font-weight:
        800;

    letter-spacing:
        0.7px;

}


.score {

    font-size:
        18px;

    font-weight:
        800;

}


.quality {

    text-align:
        left;

    font-size:
        10px;

    font-weight:
        800;

}


.extreme {

    color:
        #36ee96;

}


.very-high {

    color:
        #71efb1;

}


.high {

    color:
        #b4eb67;

}


.good {

    color:
        #f1d35b;

}


.watch {

    color:
        #f0a656;

}


.low {

    color:
        #d76a6a;

}


.rank-1 {

    color:
        #ffe34f;

}


.rank-2 {

    color:
        #d3d9e0;

}


.rank-3 {

    color:
        #eb9f62;

}


.muted {

    color:
        #7b8998;

}


.loading {

    padding:
        50px;

    text-align:
        center;

    color:
        #8fa0b2;

}


.error {

    margin-top:
        20px;

    padding:
        15px;

    border:
        1px solid #5b2932;

    background:
        #241015;

    border-radius:
        10px;

    color:
        #ff8d98;

    display:
        none;

}


.legend {

    margin-top:
        15px;

    color:
        #738296;

    font-size:
        11px;

    line-height:
        1.7;

}


@media (
    max-width:
    800px
) {

    .header {

        align-items:
            flex-start;

        flex-direction:
            column;

    }


    .live-box {

        text-align:
            left;

    }


    .summary {

        grid-template-columns:
            repeat(
                2,
                1fr
            );

    }

}

</style>

</head>


<body>


<div class="container">


    <div class="header">

        <div class="title-area">

            <h1>
                ▥ TF-Barcode Scanner
            </h1>

            <p>
                $1–$5 stocks · Last 2 trading sessions · Ranked by barcode behavior
            </p>

        </div>


        <div class="live-box">

            <div class="status">
                AUTO REFRESH
            </div>

            <div
                class="updated"
                id="updated"
            >
                Loading...
            </div>

        </div>

    </div>



    <div class="summary">

        <div class="card">

            <div class="card-label">
                Price Range
            </div>

            <div
                class="card-value"
                id="priceRange"
            >
                $1 – $5
            </div>

        </div>


        <div class="card">

            <div class="card-label">
                Candidates
            </div>

            <div
                class="card-value"
                id="candidates"
            >
                -
            </div>

        </div>


        <div class="card">

            <div class="card-label">
                Results
            </div>

            <div
                class="card-value"
                id="results"
            >
                -
            </div>

        </div>


        <div class="card">

            <div class="card-label">
                Scan Time
            </div>

            <div
                class="card-value"
                id="scanTime"
            >
                -
            </div>

        </div>

    </div>



    <div class="table-wrapper">

        <table>

            <thead>

                <tr>

                    <th>
                        #
                    </th>

                    <th>
                        Ticker
                    </th>

                    <th>
                        Price
                    </th>

                    <th>
                        Barcode
                    </th>

                    <th>
                        Quality
                    </th>

                    <th>
                        Day 1
                    </th>

                    <th>
                        Day 2
                    </th>

                    <th>
                        Weakest
                    </th>

                    <th>
                        Consistency
                    </th>

                    <th>
                        Small Bars D2
                    </th>

                    <th>
                        Tiny Steps D2
                    </th>

                    <th>
                        Repetition D2
                    </th>

                    <th>
                        Range D2
                    </th>

                    <th>
                        Volume
                    </th>

                </tr>

            </thead>


            <tbody id="tbody">

                <tr>

                    <td
                        colspan="14"
                        class="loading"
                    >
                        Scanning $1–$5 stocks...
                    </td>

                </tr>

            </tbody>

        </table>

    </div>


    <div
        class="error"
        id="error"
    >
    </div>


    <div class="legend">

        <strong>Barcode Score:</strong>
        measures compressed 1-minute bars, repeated price levels,
        very small price changes between minutes and consistency across
        both sessions.

        <br>

        A stock cannot rank highly only because of one good day:
        the weakest of the two sessions also affects the final score.

    </div>


</div>



<script>


const tbody =
    document.getElementById(
        "tbody"
    );


const updated =
    document.getElementById(
        "updated"
    );


const candidates =
    document.getElementById(
        "candidates"
    );


const results =
    document.getElementById(
        "results"
    );


const scanTime =
    document.getElementById(
        "scanTime"
    );


const errorBox =
    document.getElementById(
        "error"
    );



function numberFormat(
    value
) {

    return Number(
        value || 0
    ).toLocaleString(
        "en-US"
    );

}



function qualityClass(
    quality
) {

    if (
        quality ===
        "EXTREME"
    ) {

        return "extreme";

    }


    if (
        quality ===
        "VERY HIGH"
    ) {

        return "very-high";

    }


    if (
        quality ===
        "HIGH"
    ) {

        return "high";

    }


    if (
        quality ===
        "GOOD"
    ) {

        return "good";

    }


    if (
        quality ===
        "WATCH"
    ) {

        return "watch";

    }


    return "low";

}



function rankClass(
    rank
) {

    if (
        rank === 1
    ) {

        return "rank-1";

    }


    if (
        rank === 2
    ) {

        return "rank-2";

    }


    if (
        rank === 3
    ) {

        return "rank-3";

    }


    return "";

}



function drawRows(
    rows
) {

    if (
        !rows
        ||
        rows.length === 0
    ) {

        tbody.innerHTML = `

            <tr>

                <td
                    colspan="14"
                    class="loading"
                >
                    No barcode candidates found.
                </td>

            </tr>

        `;

        return;

    }


    let html = "";


    for (
        const row
        of rows
    ) {

        html += `

            <tr>

                <td
                    class="
                        rank
                        ${rankClass(
                            row.rank
                        )}
                    "
                >
                    ${row.rank}
                </td>


                <td class="ticker">
                    ${row.ticker}
                </td>


                <td>
                    $${Number(
                        row.price
                    ).toFixed(
                        2
                    )}
                </td>


                <td class="score">
                    ${Number(
                        row.barcode_score
                    ).toFixed(
                        1
                    )}
                </td>


                <td
                    class="
                        quality
                        ${qualityClass(
                            row.quality
                        )}
                    "
                >
                    ${row.quality}
                </td>


                <td>
                    ${Number(
                        row.day1_score
                    ).toFixed(
                        1
                    )}
                </td>


                <td>
                    ${Number(
                        row.day2_score
                    ).toFixed(
                        1
                    )}
                </td>


                <td>
                    ${Number(
                        row.weakest_day
                    ).toFixed(
                        1
                    )}
                </td>


                <td>
                    ${Number(
                        row.consistency_score
                    ).toFixed(
                        1
                    )}%
                </td>


                <td>
                    ${Number(
                        row.day2_small_bars
                    ).toFixed(
                        1
                    )}%
                </td>


                <td>
                    ${Number(
                        row.day2_tiny_steps
                    ).toFixed(
                        1
                    )}%
                </td>


                <td>
                    ${Number(
                        row.day2_repetition
                    ).toFixed(
                        1
                    )}%
                </td>


                <td>
                    ${Number(
                        row.day2_range
                    ).toFixed(
                        2
                    )}%
                </td>


                <td>
                    ${numberFormat(
                        row.day_volume
                    )}
                </td>

            </tr>

        `;

    }


    tbody.innerHTML =
        html;

}



async function loadRanking() {

    try {

        errorBox.style.display =
            "none";


        const response =
            await fetch(
                "/api/ranking?t="
                +
                Date.now(),
                {
                    cache:
                        "no-store"
                }
            );


        if (
            !response.ok
        ) {

            throw new Error(
                "HTTP "
                +
                response.status
            );

        }


        const data =
            await response.json();


        if (
            data.error
        ) {

            throw new Error(
                data.error
            );

        }


        updated.textContent =
            data.updated_at
            ||
            "-";


        candidates.textContent =
            data.candidates_analyzed
            ??
            "-";


        results.textContent =
            data.results_found
            ??
            "-";


        scanTime.textContent =
            Number(
                data.execution_seconds
                ||
                0
            ).toFixed(
                1
            )
            +
            "s";


        drawRows(
            data.ranking
        );


    } catch (
        error
    ) {

        console.error(
            error
        );


        errorBox.style.display =
            "block";


        errorBox.textContent =
            "Scanner error: "
            +
            error.message;

    }

}



loadRanking();



setInterval(
    loadRanking,
    60000
);


</script>


</body>

</html>
