import json
from pathlib import Path
from typing import Any

from src.llm import extract_instagram_username


def load_test_cases(test_file: str) -> list[dict[str, Any]]:
    test_path = Path(__file__).parent / test_file
    with open(test_path) as f:
        return json.load(f)


def calculate_accuracy(results: list[bool]) -> float:
    if not results:
        return 0.0
    correct = sum(results)
    return (correct / len(results)) * 100


def test_username_matching(actual: str | None, expected: str | None) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    return actual.lower() == expected.lower()


def run_extract_instagram_username_tests() -> None:
    test_cases = load_test_cases("extract_instagram_username_test_data.json")

    results = []
    print(f"Running {len(test_cases)} test cases for extract_instagram_username...\n")

    for i, test_case in enumerate(test_cases, 1):
        post = test_case["input"]["post"]
        images = test_case["input"].get("images", [])
        expected_relevant = test_case["expected"]["is_relevant"]
        expected_username = test_case["expected"]["username"]

        actual_relevant, actual_username = extract_instagram_username(post, images)

        relevant_match = actual_relevant == expected_relevant
        username_match = test_username_matching(actual_username, expected_username)
        passed = relevant_match and username_match

        results.append(passed)

        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"Test {i}: {status}")
        print(f"  Post ID: {test_case.get('post_id', 'N/A')}")
        print(f"  Images: {len(images)}")
        print(
            f"  Expected: is_relevant={expected_relevant}, username={expected_username}"
        )
        print(f"  Actual:   is_relevant={actual_relevant}, username={actual_username}")
        if not passed:
            if not relevant_match:
                print(f"  Mismatch: is_relevant")
            if not username_match:
                print(f"  Mismatch: username")
        print()

    accuracy = calculate_accuracy(results)
    print(f"\nResults: {sum(results)}/{len(results)} tests passed")
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
    run_extract_instagram_username_tests()
