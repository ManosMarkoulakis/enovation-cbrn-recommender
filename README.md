# enovation-cbrn-recommender

Το παρόν repository περιέχει την υλοποίηση του eNOVATION CBRN Recommender, ενός συστήματος συστάσεων που προτείνει το καταλληλότερο Κέντρο Εκπαίδευσης (Training Centre) με βάση:

-την επιλεγμένη Τεχνολογία

-το επιλεγμένο Σενάριο

## **Το σύστημα χρησιμοποιεί:**

-Apache Jena Fuseki (SPARQL endpoint)

-Knowledge Graph (CBRN Ontology)

-Αλγόριθμο Πολυκριτηριακής Βαθμολόγησης (MCDM)

-Mechanisms Explainability (κείμενο + justification graph)

## **Περιεχόμενα Repository:**

app.py                      → Backend API (Flask)
enovation_recommender.py    → Recommendation engine
templates/index.html         → Απλό UI
requirements.txt            → Python dependencies
docs/ENOVATION_Explanation_Report.pdf → Αναφορά επεξήγησης

## **Πώς τρέχει το σύστημα**

1. Εγκατάσταση βιβλιοθηκών

Σε Python περιβάλλον:

pip install -r requirements.txt

2. Εκτέλεση εφαρμογής
python app.py

## **Αναλυτική επεξήγηση της αρχιτεκτονικής, της λογικής SPARQL και του scoring υπάρχει στο:**

docs/ENOVATION_Explanation_Report.pdf

## **Author:**
<Εμμανουήλ Μίνωας Μαρκουλάκης>
<7.12.2025>
