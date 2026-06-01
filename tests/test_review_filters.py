from pathlib import Path
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReviewFilterTests(unittest.TestCase):
    def test_filters_by_status_type_and_search_text(self):
        script = """
const { filterReviewEvents } = require("./frontend/reviewFilters.js");
const events = [
  {
    index: 1,
    type: "click",
    title: "Scratch sprite movement",
    staff_note: "CYP debugged the movement script",
    cyp_quote: "I fixed the loop",
    tags: ["Scratch", "UAS"],
    highlight: true,
    selected_for_export: true,
    redactions: [],
  },
  {
    index: 2,
    type: "periodic",
    title: "Observation interval",
    staff_note: "Browsing resources",
    tags: ["context"],
    highlight: false,
    selected_for_export: false,
    redactions: [{ preset: "top_strip" }],
  },
  {
    index: 3,
    type: "click",
    title: "Roblox terrain",
    staff_note: "Selected material palette",
    tags: ["Roblox"],
    highlight: false,
    selected_for_export: true,
    redactions: [],
  },
];
const checks = {
  selected: filterReviewEvents(events, "selected", "").map((event) => event.index),
  unselected: filterReviewEvents(events, "unselected", "").map((event) => event.index),
  redacted: filterReviewEvents(events, "redacted", "").map((event) => event.index),
  click: filterReviewEvents(events, "clicks", "").map((event) => event.index),
  observation: filterReviewEvents(events, "observations", "").map((event) => event.index),
  search: filterReviewEvents(events, "all", "debugged loop").map((event) => event.index),
};
console.log(JSON.stringify(checks));
"""
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "selected": [1, 3],
                "unselected": [2],
                "redacted": [2],
                "click": [1, 3],
                "observation": [2],
                "search": [1],
            },
        )


if __name__ == "__main__":
    unittest.main()
