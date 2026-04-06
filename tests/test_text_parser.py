import unittest

from DugCanLinker.protocol import (
    PKT_MAIN, PKT_AUX, PKT_REPORT, PKT_RESPONSE, parse_text_line, parse_json_line,
)
from DugCanLinker.serial_receiver import TextLineParser


class TextLineParseTests(unittest.TestCase):
    """parse_text_line() 단위 테스트"""

    def test_parse_main_line(self):
        line = (
            "ID:0xCFDD6D1 PGN:0xFDD6 "
            "X(st=2 -=1 +=0 N=0 pos=200) "
            "Y(st=0 -=0 +=1 N=0 pos=140) "
            "B1:0 B2:1 B3:0 B4:3"
        )
        result = parse_text_line(line)
        self.assertIsNotNone(result)

        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_MAIN)
        self.assertEqual(pkt.x.position, 200)
        self.assertEqual(pkt.x.status, 2)
        self.assertEqual(pkt.x.negative, 1)
        self.assertEqual(pkt.x.positive, 0)
        self.assertEqual(pkt.x.neutral, 0)
        self.assertEqual(pkt.y.position, 140)
        self.assertEqual(pkt.y.positive, 1)
        self.assertEqual(pkt.buttons.btn1, 0)
        self.assertEqual(pkt.buttons.btn2, 1)
        self.assertEqual(pkt.buttons.btn3, 0)
        self.assertEqual(pkt.buttons.btn4, 3)

    def test_parse_aux_line(self):
        line = "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)"
        result = parse_text_line(line)
        self.assertIsNotNone(result)

        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_AUX)
        self.assertEqual(pkt.x.position, 0)
        self.assertEqual(pkt.x.neutral, 1)
        self.assertEqual(pkt.x.status, 0)

    def test_parse_lh_main_line(self):
        line = (
            "ID:0xCFDD8D0 PGN:0xFDD8 "
            "X(st=1 -=1 +=0 N=0 pos=180) "
            "Y(st=0 -=0 +=1 N=0 pos=150) "
            "B1:1 B2:0 B3:0 B4:0"
        )
        result = parse_text_line(line)
        self.assertIsNotNone(result)
        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_MAIN)
        self.assertEqual(pkt.x.position, 180)
        self.assertEqual(pkt.y.position, 150)

    def test_parse_lh_aux_line(self):
        line = "ID:0xCFDD9D0 PGN:0xFDD9 AUX_X(st=0 -=0 +=1 N=0 pos=140)"
        result = parse_text_line(line)
        self.assertIsNotNone(result)
        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_AUX)
        self.assertEqual(pkt.x.position, 140)

    def test_parse_json_report_line(self):
        line = (
            '{"type":"input_report","interval_ms":100,"streaming":true,"data":'
            '{"can_ready":true,"can_updated":true,"joystick_updated":true,"pedal_updated":true,'
            '"can_frame_count":42,"joystick_frame_count":12,"pedal_frame_count":7,'
            '"can_rx_idle_ms":8,"joystick_rx_idle_ms":6,"pedal_rx_idle_ms":9,'
            '"last_can_id":217962449,"last_joystick_can_id":217962704,"last_pedal_can_id":217963245,'
            '"joystick":{"lh":{"sa":208,"main":{"valid":true,"age_ms":7,'
            '"x":{"raw":180,"st":1,"neg":1,"pos":0,"neu":0},'
            '"y":{"raw":150,"st":0,"neg":0,"pos":1,"neu":0},'
            '"buttons":{"b1":1,"b2":0,"b3":0,"b4":0}},'
            '"aux":{"valid":true,"age_ms":5,"x":{"raw":140,"st":0,"neg":0,"pos":1,"neu":0}}},'
            '"rh":{"sa":209,"main":{"valid":false},"aux":{"valid":false}}},'
            '"pedal":{"lh":{"name":"Pedal LH","expected_sa":237,"sa":237,"valid":true,"age_ms":3,"pgn":64986,"can_id":217963245,"len":8,"data":[1,2,3,4,5,6,7,8]},'
            '"rh":{"name":"Pedal RH","expected_sa":238,"valid":false,"len":0,"data":[0,0,0,0,0,0,0,0]}},'
            '"ain":{"AIN1":321,"AIN2":322,"AIN3":323,"AIN4":324},'
            '"din":{"DIN1":false,"DIN2":true,"DIN3":false,"DIN4":false,"DIN5":false,"DIN6":false,"DIN7":false}}}'
        )
        result = parse_json_line(line)
        self.assertIsNotNone(result)
        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_REPORT)
        self.assertTrue(pkt.can_ready)
        self.assertTrue(pkt.can_updated)
        self.assertTrue(pkt.joystick_updated)
        self.assertTrue(pkt.pedal_updated)
        self.assertEqual(pkt.can_frame_count, 42)
        self.assertEqual(pkt.joystick_frame_count, 12)
        self.assertEqual(pkt.pedal_frame_count, 7)
        self.assertEqual(pkt.can_rx_idle_ms, 8)
        self.assertEqual(pkt.joystick_rx_idle_ms, 6)
        self.assertEqual(pkt.pedal_rx_idle_ms, 9)
        self.assertEqual(pkt.last_joystick_can_id, 217962704)
        self.assertEqual(pkt.last_pedal_can_id, 217963245)
        self.assertEqual(pkt.lh.sa, 208)
        self.assertTrue(pkt.lh.main.valid)
        self.assertEqual(pkt.lh.main.x.position, 180)
        self.assertTrue(pkt.pedal_lh.valid)
        self.assertEqual(pkt.pedal_lh.sa, 237)
        self.assertEqual(pkt.pedal_lh.pgn, 64986)
        self.assertEqual(pkt.pedal_lh.data[0], 1)
        self.assertEqual(pkt.pedal_lh.axis_2.neutral, 1)
        self.assertEqual(pkt.pedal_lh.axis_2.signed, 0)
        self.assertEqual(pkt.pedal_lh.axis_1.neutral, 3)
        self.assertEqual(pkt.pedal_lh.axis_1.signed, 0)
        self.assertIs(pkt.primary_pedal, pkt.pedal_lh)
        self.assertFalse(pkt.pedal_rh.valid)
        self.assertTrue(pkt.din["DIN2"])

    def test_parse_json_response_line(self):
        line = '{"result":"ok","version":"1.3.0","system_version":5,"streaming":true}'
        result = parse_json_line(line)
        self.assertIsNotNone(result)
        pkt_type, pkt = result
        self.assertEqual(pkt_type, PKT_RESPONSE)
        self.assertEqual(pkt.result, "ok")

    def test_ignores_init_message(self):
        line = "MCP2515 Init OK - Joystick CAN Reader"
        result = parse_text_line(line)
        self.assertIsNone(result)

    def test_ignores_empty_line(self):
        result = parse_text_line("")
        self.assertIsNone(result)


class TextLineParserTests(unittest.TestCase):
    """TextLineParser (바이트 단위 feed) 통합 테스트"""

    def _feed_string(self, parser: TextLineParser, text: str):
        results = []
        for ch in text.encode('ascii'):
            r = parser.feed(ch)
            if r is not None:
                results.append(r)
        return results

    def test_feed_main_line(self):
        parser = TextLineParser()
        line = (
            "ID:0xCFDD6D1 PGN:0xFDD6 "
            "X(st=0 -=1 +=0 N=0 pos=250) "
            "Y(st=0 -=0 +=0 N=0 pos=128) "
            "B1:0 B2:0 B3:0 B4:0\r\n"
        )
        results = self._feed_string(parser, line)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_MAIN)
        self.assertEqual(results[0][1].x.position, 250)
        self.assertEqual(results[0][1].y.position, 128)
        self.assertEqual(parser.stats.good, 1)

    def test_feed_aux_line(self):
        parser = TextLineParser()
        line = "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)\n"
        results = self._feed_string(parser, line)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_AUX)
        self.assertEqual(results[0][1].x.position, 0)
        self.assertEqual(results[0][1].x.neutral, 1)

    def test_skips_init_line(self):
        parser = TextLineParser()
        stream = (
            "MCP2515 Init OK - Joystick CAN Reader\r\n"
            "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)\n"
        )
        results = self._feed_string(parser, stream)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_AUX)
        self.assertEqual(parser.stats.good, 1)

    def test_multiple_lines(self):
        parser = TextLineParser()
        stream = (
            "ID:0xCFDD6D1 PGN:0xFDD6 X(st=0 -=0 +=0 N=1 pos=128) "
            "Y(st=0 -=0 +=0 N=1 pos=128) B1:0 B2:0 B3:0 B4:0\n"
            "ID:0xCFDD7D1 PGN:0xFDD7 AUX_X(st=0 -=0 +=0 N=1 pos=0)\n"
        )
        results = self._feed_string(parser, stream)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], PKT_MAIN)
        self.assertEqual(results[1][0], PKT_AUX)
        self.assertEqual(parser.stats.good, 2)

    def test_feed_json_report(self):
        parser = TextLineParser()
        line = (
            '{"type":"input_report","interval_ms":100,"streaming":true,"data":'
            '{"can_ready":true,"can_updated":false,"joystick_updated":false,"pedal_updated":false,'
            '"can_frame_count":0,"joystick_frame_count":0,"pedal_frame_count":0,'
            '"joystick":{"lh":{"sa":208,"main":{"valid":false},"aux":{"valid":false}},'
            '"rh":{"sa":209,"main":{"valid":true,"x":{"raw":128,"st":0,"neg":0,"pos":0,"neu":1},'
            '"y":{"raw":128,"st":0,"neg":0,"pos":0,"neu":1},"buttons":{"b1":0,"b2":0,"b3":0,"b4":0}},'
            '"aux":{"valid":true,"x":{"raw":120,"st":0,"neg":0,"pos":0,"neu":1}}}},'
            '"pedal":{"lh":{"name":"Pedal LH","expected_sa":237,"valid":false,"len":0,"data":[0,0,0,0,0,0,0,0]},'
            '"rh":{"name":"Pedal RH","expected_sa":238,"valid":false,"len":0,"data":[0,0,0,0,0,0,0,0]}},'
            '"ain":{"AIN1":300},"din":{"DIN1":false}}}\n'
        )
        results = self._feed_string(parser, line)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], PKT_REPORT)
        self.assertTrue(results[0][1].rh.main.valid)
        self.assertFalse(results[0][1].can_updated)
        self.assertFalse(results[0][1].joystick_updated)
        self.assertFalse(results[0][1].pedal_updated)
        self.assertEqual(parser.stats.good, 1)


if __name__ == "__main__":
    unittest.main()
