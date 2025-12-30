import json
from pathlib import Path
from typing import Any

from src.llm import analyze_sentiment


def load_test_cases(test_file: str) -> list[dict[str, Any]]:
    test_path = Path(__file__).parent / test_file
    with open(test_path) as f:
        return json.load(f)


def calculate_accuracy(results: list[bool]) -> float:
    if not results:
        return 0.0
    correct = sum(results)
    return (correct / len(results)) * 100


def compare_sentiments(
    actual: list[dict[str, str]], expected: list[dict[str, str]]
) -> list[bool]:
    results = []
    expected_dict = {item["author"]: item["sentiment"] for item in expected}

    for item in actual:
        author = item["author"]
        actual_sentiment = item["sentiment"]
        expected_sentiment = expected_dict.get(author)

        if expected_sentiment:
            match = actual_sentiment.lower() == expected_sentiment.lower()
            results.append(match)

    return results


def run_analyze_sentiment_tests() -> None:
    test_cases = load_test_cases("analyze_sentiment_test_data.json")

    all_results = []
    print(f"Running {len(test_cases)} test cases for analyze_sentiment...\n")

    for i, test_case in enumerate(test_cases, 1):
        post = test_case["input"]["post"]
        comments = test_case["input"]["comments"]
        images = test_case["input"].get("images", [])
        expected_sentiments = test_case["expected"]["sentiments"]

        actual_sentiments = analyze_sentiment(post, comments, images)

        test_results = compare_sentiments(actual_sentiments, expected_sentiments)

        status = "✓ PASS" if all(test_results) else "✗ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Post ID: {test_case.get('post_id', 'N/A')}")
        print(f"  Permalink: {test_case.get('permalink', 'N/A')}")
        print(f"  Images: {len(images)}")
        print(f"  Expected {len(expected_sentiments)} sentiments")
        print(f"  Got {len(actual_sentiments)} sentiments")

        for item in actual_sentiments:
            author = item["author"]
            actual_sentiment = item["sentiment"]
            expected_sentiment = next(
                (e["sentiment"] for e in expected_sentiments if e["author"] == author),
                "N/A",
            )

            match = (
                "✓" if actual_sentiment.lower() == expected_sentiment.lower() else "✗"
            )
            print(
                f"    {match} {author}: {actual_sentiment} (expected: {expected_sentiment})"
            )

        all_results.extend(test_results)
        print()

    accuracy = calculate_accuracy(all_results)
    print(
        f"\nResults: {sum(all_results)}/{len(all_results)} individual sentiment checks passed"
    )
    print(f"Accuracy: {accuracy:.2f}%")

    if accuracy >= 95.0:
        print("✓ PASSED - 95% accuracy threshold met")
        exit(0)
    else:
        print(
            f"✗ FAILED - 95% accuracy threshold not met (need {95.0 - accuracy:.2f}% more)"
        )
        exit(1)


if __name__ == "__main__":
    run_analyze_sentiment_tests()
