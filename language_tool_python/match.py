"""LanguageTool API Match object representation and utility module."""

import unicodedata
from collections import OrderedDict
from typing import Any, Dict, Tuple, Iterator, OrderedDict as OrderedDictType, List, Optional
from functools import total_ordering

def get_match_ordered_dict() -> OrderedDictType[str, type]:
    """
    Returns an ordered dictionary with predefined keys and their corresponding types.

    :return: An OrderedDict where each key is a string representing a specific attribute 
             and each value is the type of that attribute.
    :rtype: OrderedDictType[str, type]

    The keys and their corresponding types are:
    
    - 'ruleId': str
    - 'message': str
    - 'replacements': list
    - 'offsetInContext': int
    - 'context': str
    - 'offset': int
    - 'errorLength': int
    - 'category': str
    - 'ruleIssueType': str
    - 'sentence': str
    """
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

def auto_type(obj: Any) -> Any:
    """
    Attempts to automatically convert the input object to an integer or float.
    If the conversion to an integer fails, it tries to convert to a float.
    If both conversions fail, it returns the original object.

    :param obj: The object to be converted.
    :type obj: Any
    :return: The converted object as an integer, float, or the original object.
    :rtype: Any
    """

    try:
        return int(obj)
    except ValueError:
        try:
            return float(obj)
        except ValueError:
            return obj

def four_byte_char_positions(text: str) -> List[int]:
    """
    Identify positions of 4-byte encoded characters in a UTF-8 string.
    This function scans through the input text and identifies the positions
    of characters that are encoded with 4 bytes in UTF-8. These characters
    are typically non-BMP (Basic Multilingual Plane) characters, such as
    certain emoji and some rare Chinese, Japanese, and Korean characters.

    :param text: The input string to be analyzed.
    :type text: str
    :return: A list of positions where 4-byte encoded characters are found.
    :rtype: List[int]
    """
    positions = []
    char_index = 0
    for char in text:
        if len(char.encode('utf-8')) == 4:
            positions.append(char_index)
            # Adding 1 to the index because 4 byte characters are
            # 2 bytes in length in LanguageTool, instead of 1 byte in Python.
            char_index += 1
        char_index += 1
    return positions

@total_ordering
class Match:
    """
    Represents a match object that contains information about a language rule violation.

    :param attrib: A dictionary containing various attributes for the match.
                       The dictionary is expected to have the following keys:

                       - 'rule': A dictionary with keys 'category' (which has an 'id') and 'id', 'issueType'.

                       - 'context': A dictionary with keys 'offset' and 'text'.

                       - 'replacements': A list of dictionaries, each containing a 'value'.

                       - 'length': The length of the error.

                       - 'message': The message describing the error.
    :type attrib: Dict[str, Any]
    :param text: The original text in which the error occurred (the whole text, not just the context).
    :type text: str

    Attributes:
        PREVIOUS_MATCHES_TEXT (Optional[str]): The text of the previous match object.
        FOUR_BYTES_POSITIONS (Optional[List[int]]): The positions of 4-byte encoded characters in the text, registered by the previous match object (kept for optimization purposes if the text is the same).
        ruleId (str): The ID of the rule that was violated.
        message (str): The message describing the error.
        replacements (list): A list of suggested replacements for the error.
        offsetInContext (int): The offset of the error in the context.
        context (str): The context in which the error occurred.
        offset (int): The offset of the error.
        errorLength (int): The length of the error.
        category (str): The category of the rule that was violated.
        ruleIssueType (str): The issue type of the rule that was violated.

    Exemple of a match object received from the LanguageTool API :
    
    ```
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
    ```
    """

    PREVIOUS_MATCHES_TEXT: Optional[str] = None
    FOUR_BYTES_POSITIONS: Optional[List[int]] = None
    
    def __init__(self, attrib: Dict[str, Any], text: str) -> None:
        """
        Initialize a Match object with the given attributes.
        The method processes and normalizes the attributes before storing them on the object.
        This method adjusts the positions of 4-byte encoded characters in the text
        to ensure the offsets of the matches are correct.
        """
        if text is None:
            raise ValueError("The text parameter must not be None")
        elif not isinstance(text, str):
            raise TypeError("The text parameter must be a string")
        
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
        
        if Match.PREVIOUS_MATCHES_TEXT != text:
            Match.PREVIOUS_MATCHES_TEXT = text
            Match.FOUR_BYTES_POSITIONS = four_byte_char_positions(text)
        # Get the positions of 4-byte encoded characters in the text because without 
        # carrying out this step, the offsets of the matches could be incorrect.
        self.offset -= sum(1 for pos in Match.FOUR_BYTES_POSITIONS if pos < self.offset)

    def __repr__(self) -> str:
        """
        Return a string representation of the object.
        This method provides a detailed string representation of the object,
        including its class name and a dictionary of its attributes.

        :return: A string representation of the object.
        :rtype: str
        """
        def _ordered_dict_repr() -> str:
            """
            Generate a string representation of the object's attributes in an ordered dictionary format.

            This method collects the attributes of the object, ensuring that the order of attributes
            is preserved as defined by `get_match_ordered_dict()`. Attributes that are not part of the
            ordered dictionary are appended at the end. Attributes starting with an underscore are
            excluded from the representation.

            :return: A string representation of the object's attributes in an ordered dictionary format.
            :rtype: str
            """
            slots = list(get_match_ordered_dict())
            slots += list(set(self.__dict__).difference(slots))
            attrs = [slot for slot in slots
                     if slot in self.__dict__ and not slot.startswith('_')]
            return f"{{{', '.join([f'{attr!r}: {getattr(self, attr)!r}' for attr in attrs])}}}"

        return f'{self.__class__.__name__}({_ordered_dict_repr()})'

    def __str__(self) -> str:
        """
        Returns a string representation of the match object.

        The string includes the offset, error length, rule ID, message, 
        suggestions, and context with a visual indicator of the error position.

        :return: A formatted string describing the match object.
        :rtype: str
        """
        ruleId = self.ruleId
        s = f'Offset {self.offset}, length {self.errorLength}, Rule ID: {ruleId}'
        if self.message:
            s += f'\nMessage: {self.message}'
        if self.replacements:
            s += f"\nSuggestion: {'; '.join(self.replacements)}"
        s += f"\n{self.context}\n{' ' * self.offsetInContext + '^' * self.errorLength}"
        return s

    @property
    def matchedText(self) -> str:
        """
        Returns the substring from the context that corresponds to the matched text.

        :return: The matched text from the context.
        :rtype: str
        """
        return self.context[self.offsetInContext:self.offsetInContext+self.errorLength]

    def get_line_and_column(self, original_text: str) -> Tuple[int, int]:
        """
        Returns the line and column number of the error in the context.

        :param original_text: The original text in which the error occurred. We need this to calculate the line and column number, because the context has no more newline characters.
        :type original_text: str
        :return: A tuple containing the line and column number of the error.
        :rtype: Tuple[int, int]
        """

        context_without_additions = self.context[3:-3] if len(self.context) > 6 else self.context
        if context_without_additions not in original_text.replace('\n', ' '):
            raise ValueError('The original text does not match the context of the error')
        line = original_text.count('\n', 0, self.offset)
        column = self.offset - original_text.rfind('\n', 0, self.offset)
        return line + 1, column
    
    def select_replacement(self, index: int) -> None:
        """
        Select a single replacement suggestion based on the given index and update the replacements list, leaving only the selected replacement.

        :param index: The index of the replacement to select.
        :type index: int
        :raises ValueError: If there are no replacement suggestions.
        :raises ValueError: If the index is out of the valid range.
        """
        
        if not self.replacements:
            raise ValueError('This Match has no suggestions')
        elif index < 0 or index >= len(self.replacements):
            raise ValueError(f'This Match\'s suggestions are numbered from 0 to {len(self.replacements) - 1}')
        self.replacements = [self.replacements[index]]

    def __eq__(self, other: Any) -> bool:
        """
        Compare this object with another for equality.

        :param other: The object to compare with.
        :type other: Any
        :return: True if both objects are equal, False otherwise.
        :rtype: bool
        """
        return list(self) == list(other)

    def __lt__(self, other: Any) -> bool:
        """
        Compare this object with another object for less-than ordering.

        :param other: The object to compare with.
        :type other: Any
        :return: True if this object is less than the other object, False otherwise.
        :rtype: bool
        """
        return list(self) < list(other)

    def __iter__(self) -> Iterator[Any]:
        """
        Return an iterator over the attributes of the match object.

        This method allows the match object to be iterated over, yielding the 
        values of its attributes in the order defined by `get_match_ordered_dict`.

        :return: An iterator over the attribute values of the match object.
        :rtype: Iterator[Any]
        """
        return iter(getattr(self, attr) for attr in get_match_ordered_dict())

    def __setattr__(self, key: str, value: Any) -> None:
        """
        Set an attribute on the instance.

        This method overrides the default behavior of setting an attribute.
        It attempts to transform the value using a function from `get_match_ordered_dict()`
        based on the provided key. If the key is not found in the dictionary, the attribute
        is not set.

        :param key: The name of the attribute to set.
        :type key: str
        :param value: The value to set the attribute to.
        :type value: Any
        :raises KeyError: If the key is not found in the dictionary returned by `get_match_ordered_dict()`.
        """
        try:
            value = get_match_ordered_dict()[key](value)
        except KeyError:
            return
        super().__setattr__(key, value)

    def __getattr__(self, name: str) -> Any:
        """
        Handle attribute access for undefined attributes.

        This method is called when an attribute lookup has not found the attribute in the usual places 
        (i.e., it is not an instance attribute nor is it found in the class tree for self). This method 
        checks if the attribute name is in the ordered dictionary returned by `get_match_ordered_dict()`. 
        If the attribute name is not found, it raises an AttributeError.

        :param name: The name of the attribute being accessed.
        :type name: str
        :return: The value of the attribute if it exists.
        :rtype: Any
        :raises AttributeError: If the attribute does not exist.
        """
        if name not in get_match_ordered_dict():
            raise AttributeError(f'{self.__class__.__name__!r} object has no attribute {name!r}')
