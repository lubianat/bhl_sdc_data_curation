import SPARQLWrapper as sw
from pathlib import Path

HERE = Path(__file__).parent
ENDPOINT = "https://qlever.cs.uni-freiburg.de/api/wikidata"

QUERY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
SELECT * WHERE { ?a wdt:P356 ?doi . 
MINUS {?a wdt:P4327 ?bhl_title_id . } 
FILTER(CONTAINS(STR(?doi), "BHL.TITLE"))
}
"""

def get_results(endpoint_url, query):
    user_agent = "TiagoLubiana (tiagolubiana@gmail.com)"
    sparql = sw.SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(sw.JSON)
    return sparql.query().convert()


def main():
    results = get_results(ENDPOINT, QUERY)    
    quickstatements_for_adding_missing_bhl_ids = []
    for result in results["results"]["bindings"]:
        doi = result["doi"]["value"]
        qid = result["a"]["value"].replace("http://www.wikidata.org/entity/", "")
        bhl_id = doi.replace("10.5962/BHL.TITLE.", "")
        # test if bhl_id is a number
        try:
            int(bhl_id)
        except ValueError:
            continue
        quickstatements_for_adding_missing_bhl_ids.append(f'{qid}|P4327|"{bhl_id}"')
        
    output_file = HERE / "quickstatements_for_adding_missing_bhl_ids.txt"

    with open(output_file, "w") as f:
        f.write("\n".join(quickstatements_for_adding_missing_bhl_ids))

if __name__ == "__main__":
    main()