from flask import Flask, request, jsonify, render_template
from enovation_recommender import build_ui_payload, run_sparql
import json
from datetime import datetime
from pathlib import Path

# Flask app + feedback log location.
app = Flask(__name__)
ROOT_DIR = Path(__file__).resolve().parents[1]
FEEDBACK_FILE = ROOT_DIR / "feedback_log.jsonl"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/options", methods=["GET"])
def api_options():
    """Fetch dynamic option lists for technology and scenario labels from the KG."""
    # SPARQL queries for selectable UI options.
    q_tech = """
    PREFIX en: <http://www.semanticweb.org/eNOVATION-ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?label WHERE {
      ?s a ?type .
      ?type rdfs:subClassOf* en:Technology .
      ?s a owl:NamedIndividual .
      ?s rdfs:label ?label .
    } ORDER BY ?label
    """

    q_scen = """
    PREFIX en: <http://www.semanticweb.org/eNOVATION-ontology#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?label WHERE {
      ?s a ?type .
      ?type rdfs:subClassOf* en:Scenario .
      ?s a owl:NamedIndividual .
      ?s rdfs:label ?label .
    } ORDER BY ?label
    """

    # Run queries; keep UI responsive if the endpoint fails.
    try:
        tech_data = run_sparql(q_tech)
        scen_data = run_sparql(q_scen)

        tech_labels = [b["label"]["value"] for b in tech_data.get("results", {}).get("bindings", [])]
        scen_labels = [b["label"]["value"] for b in scen_data.get("results", {}).get("bindings", [])]
    except Exception as e:
        print(f"Error fetching dynamic options: {e}")
        tech_labels = []
        scen_labels = []

    return jsonify({"technologies": tech_labels, "scenarios": scen_labels})


@app.route("/api/recommend", methods=["GET"])
def api_recommend():
    tech = request.args.get("tech")
    scen = request.args.get("scen")
    if not tech or not scen:
        return jsonify({"error": "Missing 'tech' or 'scen' parameter"}), 400
    try:
        # Recommender output already includes scores and explanations for the UI.
        results = build_ui_payload(tech, scen)
        return jsonify({"results": results})
    except Exception as e:
        print("[/api/recommend] ERROR:", e)
        return jsonify({"error": "Internal error in recommender"}), 500


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    tech = data.get("tech")
    scen = data.get("scen")
    center_label = data.get("center_label")
    rating = data.get("rating")
    scores = data.get("scores", {})

    if not (tech and scen and center_label and rating):
        return jsonify({"error": "Missing required fields"}), 400

    # Minimal feedback record for later analysis.
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tech": tech,
        "scenario": scen,
        "center_label": center_label,
        "rating": rating,
        "scores": scores,
    }

    try:
        with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("[/api/feedback] ERROR writing file:", e)
        return jsonify({"error": "Could not save feedback"}), 500

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
