import unittest
from dataclasses import asdict
from ff11reader.domain import Character, Equipset, Macro, Slot, Text
from ff11reader.macro_links import analyze_macro_sets, is_empty, parse_reference


def txt(value=''):
    return Text(value, '', 'cp932')


def equipment(number, action='keep'):
    return Equipset(number, txt('Set'), tuple(Slot(str(i), action, None, None, None, '') for i in range(16)))


def macro(*lines, key=1):
    return Macro(1, 1, 'ctrl', key, txt('Macro'), tuple(txt(line) for line in lines))


class MacroLinksTests(unittest.TestCase):
    def test_both_commands_and_multiple_lines(self):
        c=Character('test',macros=[macro('/equipset 001','/lockstyleset 2 <wait.1>')],equipsets=[equipment(1),equipment(2,'equip'),equipment(3,'equip'),equipment(4)])
        r=analyze_macro_sets(c)
        self.assertEqual([(x.number,x.line) for x in r.empty_references],[(1,1)])
        self.assertEqual(r.unreferenced,(3,))
        self.assertEqual(len(r.for_macro(c.macros[0])),2)

    def test_remove_and_unknown_are_not_empty(self):
        self.assertTrue(is_empty(equipment(1)))
        self.assertFalse(is_empty(equipment(1,'remove')))
        self.assertFalse(is_empty(equipment(1,'unknown')))
        self.assertFalse(is_empty(Equipset(1,txt(),())))

    def test_missing_set_is_not_empty(self):
        r=analyze_macro_sets(Character('test',macros=[macro('/equipset 200')]))
        self.assertFalse(r.empty_references)
        self.assertEqual(r.references[0].target_state,'unavailable')

    def test_parser_tokens_case_wait_echo(self):
        for line in (' /EQUIPSET 001 echo <wait.1>','【/equipset】 1','/equipset 1<wait.2>'):
            self.assertEqual(parse_reference(line),('equipset',1))
        self.assertEqual(parse_reference('【/lockstyleset】 200'),('lockstyleset',200))

    def test_chat_and_nonliteral_numbers_are_not_references(self):
        for line in ('/echo /equipset 1','//equipset 1','/equipset 201','/equipset 0','/equipset 1abc','/equipset <var>','/equipset １'):
            self.assertIsNone(parse_reference(line),line)

    def test_reverse_references_keep_addresses_and_lines(self):
        c=Character('test',macros=[macro('/equipset 1','/equipset 1'),macro('/lockstyleset 1',key=2)],equipsets=[equipment(1)])
        self.assertEqual(len(analyze_macro_sets(c).for_set(1)),3)
        self.assertFalse(analyze_macro_sets(c).unreferenced)

    def test_isolation_and_no_mutation(self):
        c=Character('one',equipsets=[equipment(1,'equip')]);before=asdict(c)
        analyze_macro_sets(Character('two',macros=[macro('/equipset 1')]))
        self.assertEqual(analyze_macro_sets(c).unreferenced,(1,))
        self.assertEqual(before,asdict(c))

    def test_recomputed_after_content_changes(self):
        c=Character('test',macros=[macro('/equipset 1')],equipsets=[equipment(1)])
        self.assertTrue(analyze_macro_sets(c).empty_references)
        c.equipsets=[equipment(1,'remove')]
        self.assertFalse(analyze_macro_sets(c).empty_references)

    def test_reference_with_trailing_options(self):
        for line in ('/equipset 47 echo <wait 2>', '/equipset 47 <wait.2>',
                     '/equipset 47 echo comment', '/equipset 47 /echo hello'):
            self.assertEqual(parse_reference(line), ('equipset', 47))
        c=Character('test',macros=[macro('/equipset 47 echo <wait 2>')],equipsets=[equipment(47,'equip')])
        result=analyze_macro_sets(c)
        self.assertEqual(len(result.for_set(47)),1)
        self.assertNotIn(47,result.unreferenced)
