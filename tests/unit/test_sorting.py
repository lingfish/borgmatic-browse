import typing

import pytest
import textual.widgets
import textual.widgets.option_list
from flexmock import flexmock

from borgmatic_browse import sorting as module


class Fruit_list(module.Sortable, textual.widgets.OptionList):
    '''
    A minimal sortable option list, with options that carry a size.
    '''

    SORT_MODES = ('name', 'size', 'age')
    DEFAULT_SORT_MODE = 'name'
    DEFAULT_REVERSED: typing.ClassVar[dict] = {'name': False, 'size': True, 'age': False}

    def __init__(self, **kwargs):
        super().__init__()
        self.init_sort(**kwargs)

    def sort_options(self, options):
        key = {
            'name': lambda option: option.id,
            'size': lambda option: option.size,
            'age': lambda option: -option.size,
        }[self.sort_mode]

        return sorted(options, key=key, reverse=self.sort_reversed)


def make_fruit_list(**kwargs):
    fruit_list = Fruit_list(**kwargs)

    for option_id, size in (('pear', 2), ('apple', 3), ('fig', 1)):
        option = textual.widgets.option_list.Option(option_id, id=option_id)
        option.size = size
        fruit_list.add_option(option)

    return fruit_list


def option_ids(option_list):
    return [option.id for option in option_list.options]


def test_init_sort_defaults_to_default_mode_and_its_direction():
    fruit_list = Fruit_list()

    assert fruit_list.sort_mode == 'name'
    assert fruit_list.sort_reversed is False
    assert fruit_list.border_subtitle == 'sort: name ↑'


def test_init_sort_with_mode_uses_that_modes_default_direction():
    fruit_list = Fruit_list(sort_mode='size')

    assert fruit_list.sort_mode == 'size'
    assert fruit_list.sort_reversed is True
    assert fruit_list.border_subtitle == 'sort: size ↓'


def test_init_sort_with_mode_and_direction_uses_both():
    fruit_list = Fruit_list(sort_mode='size', sort_reversed=False)

    assert fruit_list.sort_mode == 'size'
    assert fruit_list.sort_reversed is False
    assert fruit_list.border_subtitle == 'sort: size ↑'


def test_init_sort_with_direction_only_keeps_default_mode():
    fruit_list = Fruit_list(sort_reversed=True)

    assert fruit_list.sort_mode == 'name'
    assert fruit_list.sort_reversed is True
    assert fruit_list.border_subtitle == 'sort: name ↓'


def test_set_sort_mode_sorts_options_and_updates_subtitle():
    fruit_list = make_fruit_list()

    fruit_list.set_sort_mode('size')

    assert fruit_list.sort_mode == 'size'
    assert option_ids(fruit_list) == ['apple', 'pear', 'fig']
    assert fruit_list.border_subtitle == 'sort: size ↓'


def test_set_sort_mode_resets_direction_to_the_modes_default():
    fruit_list = make_fruit_list()
    fruit_list.action_reverse_sort()
    assert fruit_list.sort_reversed is True

    fruit_list.set_sort_mode('age')

    assert fruit_list.sort_reversed is False
    assert fruit_list.border_subtitle == 'sort: age ↑'

    fruit_list.set_sort_mode('size')
    fruit_list.action_reverse_sort()
    fruit_list.set_sort_mode('size')

    assert fruit_list.sort_reversed is True


def test_action_cycle_sort_moves_through_modes_and_wraps_around():
    fruit_list = make_fruit_list()
    modes = []

    for _ in range(4):
        fruit_list.action_cycle_sort()
        modes.append(fruit_list.sort_mode)

    assert modes == ['size', 'age', 'name', 'size']


def test_action_cycle_sort_resets_direction_and_sorts():
    fruit_list = make_fruit_list()
    fruit_list.action_reverse_sort()

    fruit_list.action_cycle_sort()

    assert fruit_list.sort_mode == 'size'
    assert fruit_list.sort_reversed is True
    assert option_ids(fruit_list) == ['apple', 'pear', 'fig']


def test_action_reverse_sort_flips_direction_and_sorts():
    fruit_list = make_fruit_list()

    fruit_list.action_reverse_sort()

    assert fruit_list.sort_reversed is True
    assert option_ids(fruit_list) == ['pear', 'fig', 'apple']
    assert fruit_list.border_subtitle == 'sort: name ↓'

    fruit_list.action_reverse_sort()

    assert fruit_list.sort_reversed is False
    assert option_ids(fruit_list) == ['apple', 'fig', 'pear']
    assert fruit_list.border_subtitle == 'sort: name ↑'


def test_apply_sort_orders_options_the_way_sort_options_does():
    fruit_list = make_fruit_list()
    assert option_ids(fruit_list) == ['pear', 'apple', 'fig']

    fruit_list.apply_sort()

    assert option_ids(fruit_list) == ['apple', 'fig', 'pear']


def test_apply_sort_keeps_highlighted_option_highlighted_by_id():
    fruit_list = make_fruit_list()
    fruit_list.highlighted = 0
    assert fruit_list.options[fruit_list.highlighted].id == 'pear'

    fruit_list.apply_sort()

    assert fruit_list.options[fruit_list.highlighted].id == 'pear'
    assert fruit_list.highlighted == 2


def test_apply_sort_with_nothing_highlighted_leaves_nothing_highlighted():
    fruit_list = make_fruit_list()
    fruit_list.highlighted = None

    fruit_list.apply_sort()

    assert fruit_list.highlighted is None
    assert option_ids(fruit_list) == ['apple', 'fig', 'pear']


def test_apply_sort_updates_subtitle():
    fruit_list = make_fruit_list()
    fruit_list.sort_mode = 'age'
    fruit_list.sort_reversed = True

    fruit_list.apply_sort()

    assert fruit_list.border_subtitle == 'sort: age ↓'


@pytest.mark.parametrize(
    'sort_reversed,arrow',
    ((True, '↓'), (False, '↑')),
)
def test_border_subtitle_shows_mode_then_direction_arrow(sort_reversed, arrow):
    fruit_list = Fruit_list(sort_mode='age', sort_reversed=sort_reversed)

    assert fruit_list.border_subtitle == f'sort: age {arrow}'


def test_apply_sort_with_options_already_in_order_does_not_rebuild_them():
    fruit_list = make_fruit_list()
    fruit_list.apply_sort()
    fruit_list.highlighted = 1
    flexmock(fruit_list).should_receive('clear_options').never()
    flexmock(fruit_list).should_receive('add_options').never()

    fruit_list.apply_sort()

    assert option_ids(fruit_list) == ['apple', 'fig', 'pear']
    assert fruit_list.highlighted == 1
