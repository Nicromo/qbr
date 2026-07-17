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


class TestTelegramSplit(unittest.TestCase):

    def test_short_message_no_split(self):
        from telegram import _split
        text = "Hello world"
        result = _split(text)
        self.assertEqual(result, ["Hello world"])

    def test_exact_limit(self):
        from telegram import _split
        text = "x" * 4096
        result = _split(text)
        self.assertEqual(len(result), 1)

    def test_long_message_splits(self):
        from telegram import _split
        text = ("line\n" * 2000)
        result = _split(text)
        self.assertGreater(len(result), 1)
        for chunk in result:
            self.assertLessEqual(len(chunk), 4096)

    def test_no_newlines_hard_cut(self):
        from telegram import _split
        text = "x" * 5000
        result = _split(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(result[0]), 4096)

    def test_split_preserves_all_content(self):
        from telegram import _split
        lines = [f"line {i}\n" for i in range(500)]
        text = "".join(lines)
        result = _split(text)
        joined = "".join(result)
        self.assertEqual(joined.replace("\n", "").replace(" ", ""),
                         text.replace("\n", "").replace(" ", ""))


class TestTelegramSend(unittest.TestCase):

    @patch("telegram.requests.post")
    def test_send_success(self, mock_post):
        from telegram import send
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        send("test message")

        mock_post.assert_called_once()
        call_data = mock_post.call_args
        self.assertEqual(call_data.kwargs["data"]["text"], "test message")

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
    def test_finds_student(self, mock_get):
        html = """
        <html><body>
        <table>
        <tr>
            <td>5</td><td>Иванов</td><td>ЕГЭ</td><td>250</td>
            <td>80</td><td>85</td><td>85</td><td>3</td>
            <td>Да</td><td>1</td>
        </tr>
        <tr>
            <td>12</td><td>Петров</td><td>ЕГЭ</td><td>230</td>
            <td>75</td><td>80</td><td>75</td><td>5</td>
            <td>Нет</td><td>2</td>
        </tr>
        </table>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://test.url"
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from mtuci import get_group_info
        with patch("mtuci.MY_CODE", "2164745"):
            result = get_group_info("https://test.url")
            self.assertIsNone(result["my"])

    @patch("mtuci.requests.get")
    def test_code_found(self, mock_get):
        html = """
        <table>
        <tr>
            <td>7</td><td>2164745</td><td>ЕГЭ</td><td>260</td>
            <td>90</td><td>85</td><td>85</td><td>4</td>
            <td>Да</td><td>1</td>
        </tr>
        </table>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://test.url"
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from mtuci import get_group_info
        result = get_group_info("https://test.url")
        self.assertIsNotNone(result["my"])
        self.assertEqual(result["my"]["place"], "7")
        self.assertEqual(result["my"]["scores"], "260")
        self.assertEqual(result["my"]["priority"], "1")

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
        mock_resp.text = "<html><body>No tables here</body></html>"
        mock_get.return_value = mock_resp

        from mtuci import get_group_info
        result = get_group_info("https://test.url")
        self.assertIsNone(result["my"])


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
        self.assertIsNotNone(result["my"])
        self.assertEqual(result["my"]["place"], 3)
        self.assertEqual(result["my"]["to_pass"], 3 - 50)
        self.assertEqual(result["direction"], "Информатика")
        self.assertEqual(result["places"], 50)

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
        self.assertEqual(result["update_time"], "?")

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

    @patch("main.send")
    @patch("main.build_mtuci_section", return_value="МТУСИ OK\n")
    @patch("main.build_misis_section", side_effect=Exception("МИСИС down"))
    @patch("main.build_rea_section", return_value="РЭУ OK\n")
    def test_one_failure_doesnt_kill_all(self, mock_rea, mock_misis, mock_mtuci, mock_send):
        from main import main
        main()

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][0]
        self.assertIn("РЭУ OK", sent_text)
        self.assertIn("МТУСИ OK", sent_text)
        self.assertIn("МИСИС: ошибка получения данных", sent_text)

    @patch("main.send")
    @patch("main.build_mtuci_section", side_effect=Exception("down"))
    @patch("main.build_misis_section", side_effect=Exception("down"))
    @patch("main.build_rea_section", side_effect=Exception("down"))
    def test_all_failures_still_sends(self, mock_rea, mock_misis, mock_mtuci, mock_send):
        from main import main
        main()

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][0]
        self.assertIn("РЭУ", sent_text)
        self.assertIn("МИСИС", sent_text)
        self.assertIn("МТУСИ", sent_text)


class TestReaModule(unittest.TestCase):

    @patch("rea.requests.get")
    def test_get_all_my_data(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"rating": 5, "priority": 1}]
        mock_get.return_value = mock_resp

        from rea import get_all_my_data
        result = get_all_my_data()
        self.assertEqual(len(result), 1)

    @patch("rea.requests.get")
    def test_get_group_info_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"competitive_group_name": "Экономика"}]
        mock_get.return_value = mock_resp

        from rea import get_group_info
        result = get_group_info("test-id")
        self.assertEqual(result["competitive_group_name"], "Экономика")

    @patch("rea.requests.get")
    def test_get_group_info_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        from rea import get_group_info
        result = get_group_info("test-id")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
