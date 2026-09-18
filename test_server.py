import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import create_server
from sim import preset


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def get_json(self, path):
        with urlopen(self.url + path, timeout=5) as response:
            return response.status, json.load(response)

    def test_health_and_bootstrap(self):
        status, health = self.get_json("/api/health")
        self.assertEqual(status, 200); self.assertTrue(health["ok"])
        status, data = self.get_json("/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertEqual(set(data["presets"]), {"protection", "retribution"})
        self.assertEqual(set(data["phase6_bis"]), {"protection", "retribution"})
        self.assertEqual(sum(len(tree["talents"]) for tree in data["talent_data"]["trees"]), 52)
        self.assertTrue(all(url.startswith("https://www.wowhead.com/forever/") for url in data["sources"].values()))

    def test_browser_assets(self):
        for path, marker in [("/", b"Forever Sims"), ("/paladin.html", b"Forever Paladin Simulator"),
                             ("/all-specs.html", b"Back to all specs"), ("/styles.css", b"--pink"),
                             ("/app.js", b"ForeverSim.simulate"), ("/home.js", b"data/specs.json")]:
            with self.subTest(path=path), urlopen(self.url + path, timeout=5) as response:
                self.assertEqual(response.status, 200); self.assertIn(marker, response.read())
        with urlopen(self.url + "/item-icons/inv_helmet_72.jpg", timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "image/jpeg")
            self.assertGreater(len(response.read()), 500)

    def test_default_comparison_pages_and_endpoint(self):
        for path in ("/dps-comparison.html","/tank-comparison.html"):
            with urlopen(self.url+path,timeout=5) as response:
                self.assertEqual(response.status,200);self.assertIn(b"Default profile comparisons",response.read())
        with urlopen(self.url+"/api/benchmarks",timeout=30) as response:
            data=json.load(response)
        self.assertEqual(len(data["rows"]),148*len(data["target_counts"]))
        self.assertEqual(data["duration"],120)
        self.assertEqual(sum(x["role"]=="tank" for x in data["rows"]),17*len(data["target_counts"]))
        self.assertTrue(all(x["race"] for x in data["rows"]))
        self.assertTrue(all(x["dps"]>0 and x["tps"]>0 for x in data["rows"]))

    def test_classic_item_catalog_endpoint(self):
        status, data = self.get_json("/api/items")
        self.assertEqual(status, 200)
        self.assertTrue(data["version"].startswith("wow-classic-items-"))
        self.assertGreater(len(data["items"]), 2000)
        self.assertTrue(all(item["wowhead"].startswith("https://www.wowhead.com/classic/item=")
                            for item in data["items"]))

    def test_simulation_endpoint(self):
        profile = preset("retribution"); profile["duration"] = 10; profile["iterations"] = 2
        req = Request(self.url + "/api/simulate", data=json.dumps({"profile": profile}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=5) as response:
            data = json.load(response)
        self.assertEqual(response.status, 200); self.assertEqual(data["profile"]["spec"], "retribution")
        self.assertIn("dps", data["metrics"]); self.assertIn("first_iteration", data)

    def test_invalid_profile_is_400(self):
        req = Request(self.url + "/api/simulate", data=b'{"profile":{}}',
                      headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as context:
            urlopen(req, timeout=5)
        self.assertEqual(context.exception.code, 400)
        self.assertIn("error", json.load(context.exception))

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(self.url + "/..%2f..%2fdata.json", timeout=5)
        self.assertEqual(context.exception.code, 404)


if __name__ == "__main__": unittest.main()
