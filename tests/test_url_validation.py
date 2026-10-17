import unittest

from spotify_transcript_app.url_validation import EpisodeUrlError, parse_episode_url


VALID_ID = "0123456789ABCDEFGHIJKL"


class EpisodeUrlTests(unittest.TestCase):
    def test_accepts_regular_episode_url(self):
        result = parse_episode_url(
            f"https://open.spotify.com/episode/{VALID_ID}?si=abc123"
        )
        self.assertEqual(result.episode_id, VALID_ID)
        self.assertEqual(
            result.canonical_url,
            f"https://open.spotify.com/episode/{VALID_ID}",
        )

    def test_accepts_localized_episode_url(self):
        result = parse_episode_url(
            f"https://open.spotify.com/intl-de/episode/{VALID_ID}"
        )
        self.assertEqual(result.episode_id, VALID_ID)

    def test_rejects_unsafe_or_wrong_inputs(self):
        invalid = [
            "",
            f"http://open.spotify.com/episode/{VALID_ID}",
            f"https://open.spotify.com.example/episode/{VALID_ID}",
            f"https://open.spotify.com/show/{VALID_ID}",
            "https://open.spotify.com/episode/too-short",
            f"https://user:secret@open.spotify.com/episode/{VALID_ID}",
            f"https://open.spotify.com:443/episode/{VALID_ID}",
            VALID_ID,
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(EpisodeUrlError):
                    parse_episode_url(value)


if __name__ == "__main__":
    unittest.main()

