import unittest
from unittest.mock import patch, MagicMock
import json
import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")


class TestCleanName(unittest.TestCase):

    def test_removes_keywords(self):
        from main import clean_name
        self.assertEqual(clean_name("Только РФ Очная Москва Экономика"), "Экономика")

    def test_removes_reu(self):
        from main import clean_name
        result = clean_name("РЭУ им. Г.В. Плеханова ВШКМиС Менеджмент")
        self.assertEqual(result, "Менеджмент")

    def test_cleans_extra_commas(self):
        from main import clean_name
        result = clean_name("Только, , , Математика")
        self.assertEqual(result, "Математика")

    def test_strips_wrapping_chars(self):
        from main import clean_name
        result = clean_name("  (Информатика) ,")
        self.assertEqual(result, "Информатика")

    def test_empty_after_cleaning(self):
        from main import clean_name
        result = clean_name("Только РФ")
        self.assertEqual(result, "")


class TestEscapeHtml(unittest.TestCase):

    def test_escapes_angle_brackets(self):
        from main import esc
        self.assertEqual(esc("<b>test</b>"), "&lt;b&gt;test&lt;/b&gt;")

    def test_escapes_ampersand(self):
        from main import esc
        self.assertEqual(esc("A & B"), "A &amp; B")

    def test_plain_text_unchanged(self):
        from main import esc
        self.assertEqual(esc("Информатика"), "Информатика")

    def test_handles_numbers(self):
        from main import esc
        self.assertEqual(esc(42), "42")


class TestPassIndicator(unittest.TestCase):

    def test_passing(self):
        from main import pass_indicator
        result = pass_indicator(-3)
        self.assertIn("Проходишь", result)

    def test_zero_passes(self):
        from main import pass_indicator
        result = pass_indicator(0)
        self.assertIn("Проходишь", result)

    def test_almost(self):
        from main import pass_indicator
        result = pass_indicator(3)
        self.assertIn("Почти", result)

    def test_far(self):
        from main import pass_indicator
        result = pass_indicator(15)
        self.assertIn("15", result)

    def test_string_passthrough(self):
        from main import pass_indicator
        self.assertEqual(pass_indicator("-"), "-")


class TestStorage(unittest.TestCase):

    def test_get_delta_new_entry(self):
        from storage import get_delta
        self.assertIsNone(get_delta("key", 5, {}))

    def test_get_delta_improved(self):
        from storage import get_delta
        old = {"key": {"place": 10}}
        self.assertEqual(get_delta("key", 7, old), 3)

    def test_get_delta_worsened(self):
        from storage import get_delta
        old = {"key": {"place": 5}}
        self.assertEqual(get_delta("key", 8, old), -3)

    def test_get_delta_unchanged(self):
        from storage import get_delta
        old = {"key": {"place": 5}}
        self.assertEqual(get_delta("key", 5, old), 0)

    def test_delta_str_new(self):
        from storage import delta_str
        self.assertIn("🆕", delta_str(None))

    def test_delta_str_up(self):
        from storage import delta_str
        result = delta_str(3)
        self.assertIn("⬆️", result)
        self.assertIn("+3", result)

    def test_delta_str_down(self):
        from storage import delta_str
        result = delta_str(-2)
        self.assertIn("⬇️", result)

    def test_delta_str_same(self):
        from storage import delta_str
        self.assertIn("➖", delta_str(0))

    def test_has_changes_empty_old(self):
        from storage import has_changes
        self.assertTrue(has_changes({}, {"a": {"place": 1}}))

    def test_has_changes_same(self):
        from storage import has_changes
        data = {"a": {"place": 5}}
        self.assertFalse(has_changes(data, data))

    def test_has_changes_different(self):
        from storage import has_changes
        old = {"a": {"place": 5}}
        new = {"a": {"place": 3}}
        self.assertTrue(has_changes(old, new))

    def test_has_changes_entry_removed(self):
        from storage import has_changes
        old = {"a": {"place": 5}, "b": {"place": 10}}
        new = {"a": {"place": 5}}
        self.assertTrue(has_changes(old, new))


class TestBuildSummary(unittest.TestCase):

    def test_summary_mixed(self):
        from main import build_summary
        data = {
            "a": {"place": 10, "places": 50},
            "b": {"place": 53, "places": 50},
            "c": {"place": 60, "places": 50},
        }
        result = build_summary(data)
        self.assertIn("✅", result)
        self.assertIn("🟡", result)
        self.assertIn("🔴", result)

    def test_summary_all_passing(self):
        from main import build_summary
        data = {
            "a": {"place": 10, "places": 50},
            "b": {"place": 30, "places": 50},
        }
        result = build_summary(data)
        self.assertIn("✅ 2", result)
        self.assertNotIn("🔴", result)

    def test_summary_no_data(self):
        from main import build_summary
        self.assertEqual(build_summary({}), "")


class TestTelegramSplit(unittest.TestCase):

    def test_short_message_no_split(self):
        from telegram import _split
        result = _split("Hello world")
        self.assertEqual(result, ["Hello world"])

    def test_exact_limit(self):
        from telegram import _split
        result = _split("x" * 4096)
        self.assertEqual(len(result), 1)

    def test_long_message_splits(self):
        from telegram import _split
        result = _split("line\n" * 2000)
        self.assertGreater(len(result), 1)
        for chunk in result:
            self.assertLessEqual(len(chunk), 4096)

    def test_no_newlines_hard_cut(self):
        from telegram import _split
        result = _split("x" * 5000)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 4096)


class TestTelegramSend(unittest.TestCase):

    @patch("telegram.requests.post")
    def test_send_with_parse_mode(self, mock_post):
        from telegram import send
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        send("<b>test</b>")
        call_data = mock_post.call_args
        self.assertEqual(call_data.kwargs["data"]["parse_mode"], "HTML")

    @patch("telegram.requests.post")
    def test_send_raises_on_error(self, mock_post):
        from telegram import send
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        mock_resp.raise_for_status.side_effect = Exception("400")
        mock_post.return_value = mock_resp

        with self.assertRaises(Exception):
            send("test")


class TestMtuciParser(unittest.TestCase):

    @patch("mtuci.requests.get")
    def test_code_found(self, mock_get):
        html = """
        <table><tr>
            <td>7</td><td>2164745</td><td>ЕГЭ</td><td>260</td>
            <td>90</td><td>85</td><td>85</td><td>4</td>
            <td>Да</td><td>1</td>
        </tr></table>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://test.url"
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from mtuci import get_group_info
        result = get_group_info("https://test.url")
        self.assertEqual(result["my"]["place"], "7")
        self.assertEqual(result["my"]["scores"], "260")

    @patch("mtuci.requests.get")
    def test_not_enough_columns(self, mock_get):
        html = "<table><tr><td>2164745</td><td>data</td></tr></table>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://test.url"
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from mtuci import get_group_info
        result = get_group_info("https://test.url")
        self.assertIsNone(result["my"])

    @patch("mtuci.requests.get")
    def test_no_tables(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://test.url"
        mock_resp.text = "<html><body>No tables</body></html>"
        mock_get.return_value = mock_resp

        from mtuci import get_group_info
        self.assertIsNone(get_group_info("https://test.url")["my"])


class TestMisisParser(unittest.TestCase):

    @patch("misis.requests.get")
    def test_finds_student(self, mock_get):
        html = """
        <html><body>
        <date>01.07.2026</date>
        <direction>Информатика</direction>
        <itog>50</itog>
        <table><tbody>
        <tr>
            <td>3</td><td>Иванов</td><td>2164745</td><td>1</td>
            <td>да</td><td>250</td><td>5</td>
        </tr>
        </tbody></table>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from misis import get_group_info
        result = get_group_info("test-group")
        self.assertEqual(result["my"]["place"], 3)
        self.assertEqual(result["my"]["to_pass"], -47)

    @patch("misis.requests.get")
    def test_missing_custom_tags(self, mock_get):
        html = """
        <html><body>
        <table><tbody>
        <tr><td>1</td><td>X</td><td>9999</td><td>1</td></tr>
        </tbody></table>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from misis import get_group_info
        result = get_group_info("test-group")
        self.assertEqual(result["direction"], "test-group")
        self.assertEqual(result["places"], 0)

    @patch("misis.requests.get")
    def test_no_table_raises(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>No table</body></html>"
        mock_get.return_value = mock_resp

        from misis import get_group_info
        with self.assertRaises(RuntimeError):
            get_group_info("test-group")


class TestMainErrorHandling(unittest.TestCase):

    @patch("main.storage")
    @patch("main.send")
    @patch("main.build_mtuci_section")
    @patch("main.build_misis_section", side_effect=Exception("МИСИС down"))
    @patch("main.build_rea_section")
    def test_one_failure_doesnt_kill_all(self, mock_rea, mock_misis, mock_mtuci, mock_send, mock_storage):
        mock_storage.load.return_value = {}
        mock_storage.has_changes.return_value = True
        mock_rea.return_value = "РЭУ OK\n"
        mock_mtuci.return_value = "МТУСИ OK\n"

        from main import main
        main()

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][0]
        self.assertIn("РЭУ OK", sent_text)
        self.assertIn("МТУСИ OK", sent_text)
        self.assertIn("ошибка получения данных", sent_text)


class TestReaModule(unittest.TestCase):

    @patch("rea.requests.get")
    def test_get_all_my_data(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"rating": 5, "priority": 1}]
        mock_get.return_value = mock_resp

        from rea import get_all_my_data
        self.assertEqual(len(get_all_my_data()), 1)

    @patch("rea.requests.get")
    def test_get_group_info_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"competitive_group_name": "Экономика"}]
        mock_get.return_value = mock_resp

        from rea import get_group_info
        self.assertEqual(get_group_info("test-id")["competitive_group_name"], "Экономика")

    @patch("rea.requests.get")
    def test_get_group_info_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        from rea import get_group_info
        self.assertIsNone(get_group_info("test-id"))


if __name__ == "__main__":
    unittest.main()
