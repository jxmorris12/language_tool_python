import unicodedata
from collections import OrderedDict
from functools import total_ordering

def get_match_ordered_dict():
    slots = OrderedDict([
        ('ruleId', str), 
        ('message', str),
        ('replacements', list),
        ('offsetInContext', int), 
        ('context', str), 
        ('offset', int), 
        ('errorLength', int),
        ('category', str), 
        ('ruleIssueType', str),
        ('sentence', str), 
    ])
    return slots

""" Sample match JSON:
    {
        'message': 'Possible spelling mistake found.', 
        'shortMessage': 'Spelling mistake', 
        'replacements': [{'value': 'newt'}, {'value': 'not'}, {'value': 'new', 'shortDescription': 'having just been made'}, {'value': 'news'}, {'value': 'foot', 'shortDescription': 'singular'}, {'value': 'root', 'shortDescription': 'underground organ of a plant'}, {'value': 'boot'}, {'value': 'noon'}, {'value': 'loot', 'shortDescription': 'plunder'}, {'value': 'moot'}, {'value': 'Root'}, {'value': 'soot', 'shortDescription': 'carbon black'}, {'value': 'newts'}, {'value': 'nook'}, {'value': 'Lieut'}, {'value': 'coot'}, {'value': 'hoot'}, {'value': 'toot'}, {'value': 'snoot'}, {'value': 'neut'}, {'value': 'nowt'}, {'value': 'Noor'}, {'value': 'noob'}], 
        'offset': 8, 
        'length': 4, 
        'context': {'text': 'This is noot okay. ', 'offset': 8, 'length': 4}, 'sentence': 'This is noot okay.', 
        'type': {'typeName': 'Other'}, 
        'rule': {'id': 'MORFOLOGIK_RULE_EN_US', 'description': 'Possible spelling mistake', 'issueType': 'misspelling', 'category': {'id': 'TYPOS', 'name': 'Possible Typo'}}, 
        'ignoreForIncompleteSentence': False, 
        'contextForSureMatch': 0
    }

"""
def auto_type(obj):
    try:
        return int(obj)
    except ValueError:
        try:
            return float(obj)
        except ValueError:
            return obj

@total_ordering
class Match:
    """Hold information about where a rule matches text."""
    def __init__(self, attrib):
        # Process rule.
        attrib['category'] = attrib['rule']['category']['id']
        attrib['ruleId'] = attrib['rule']['id']
        attrib['ruleIssueType'] = attrib['rule']['issueType']
        del attrib['rule']
        # Process context.
        attrib['offsetInContext'] = attrib['context']['offset']
        attrib['context'] = attrib['context']['text']
        # Process replacements.
        attrib['replacements'] = [r['value'] for r in attrib['replacements']]
        # Rename error length.
        attrib['errorLength'] = attrib['length']
        # Normalize unicode
        attrib['message'] = unicodedata.normalize("NFKC", attrib['message'])
        # Store objects on self.
        for k, v in attrib.items():
            setattr(self, k, v)

    def __repr__(self):
        def _ordered_dict_repr():
            slots = list(get_match_ordered_dict())
            slots += list(set(self.__dict__).difference(slots))
            attrs = [slot for slot in slots
                     if slot in self.__dict__ and not slot.startswith('_')]
            return '{{{}}}'.format(
                ', '.join([
                    '{!r}: {!r}'.format(attr, getattr(self, attr))
                    for attr in attrs
                ])
            )

        return '{}({})'.format(self.__class__.__name__, _ordered_dict_repr())

    def __str__(self):
        ruleId = self.ruleId
        s = 'Offset {}, length {}, Rule ID: {}'.format(
            self.offset, self.errorLength, ruleId)
        if self.message:
            s += '\nMessage: {}'.format(self.message)
        if self.replacements:
            s += '\nSuggestion: {}'.format('; '.join(self.replacements))
        s += '\n{}\n{}'.format(
            self.context, ' ' * self.offsetInContext + '^' * self.errorLength
        )
        return s

    @property
    def matchedText(self):
        """ Returns the text that garnered the error (without its surrounding context).
        """
        return self.context[self.offsetInContext:self.offsetInContext+self.errorLength]

    def __eq__(self, other):
        return list(self) == list(other)

    def __lt__(self, other):
        return list(self) < list(other)

    def __iter__(self):
        return iter(getattr(self, attr) for attr in get_match_ordered_dict())

    def __setattr__(self, key, value):
        try:
            value = get_match_ordered_dict()[key](value)
        except KeyError:
            return
        super().__setattr__(key, value)

    def __getattr__(self, name):
        if name not in get_match_ordered_dict():
            raise AttributeError('{!r} object has no attribute {!r}'
                                 .format(self.__class__.__name__, name))
