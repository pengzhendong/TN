# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright (c) 2024, WENET COMMUNITY.  Xingchen Song (sxc19@tsinghua.org.cn).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pynini import accep, cross, string_file
from pynini.lib.pynutil import add_weight, delete, insert

from tn.processor import Processor
from tn.utils import get_abs_path, load_labels
from tn.english.rules.cardinal import Cardinal
from tn.english.rules.decimal import Decimal
from tn.english.rules.measure import SINGULAR_TO_PLURAL

maj_singular = string_file((get_abs_path("english/data/money/currency_major.tsv")))


class Money(Processor):

    def __init__(self, deterministic: bool = False):
        """
        Args:
            deterministic: if True will provide a single transduction option,
                for False multiple transduction are generated (used for audio-based normalization)
        """
        super().__init__("money", ordertype="en_tn")
        self.deterministic = deterministic
        self.build_tagger()
        self.build_verbalizer()

    def build_tagger(self):
        """
        Finite state transducer for classifying money, suppletive aware, e.g.
            $12.05 -> money { currency_maj: "dollars" integer_part: "twelve"  fractional_part: "oh five" }
            $12.0500 -> money { currency_maj: "dollars" integer_part: "twelve"  fractional_part: "oh five" }
            $1 -> money { currency_maj: "dollar" integer_part: "one" }
            $1.00 -> money { currency_maj: "dollar" integer_part: "one" }
            $0.05 -> money { currency_maj: "dollars" integer_part: "zero"  fractional_part: "oh five" }
            $1 million -> money { currency_maj: "dollars" integer_part: "one" quantity: "million" }
            $1.2 million -> money { currency_maj: "dollars" integer_part: "one"  fractional_part: "two" quantity: "million" }
            $1.2320 -> money { currency_maj: "dollars" integer_part: "one"  fractional_part: "two three two" }
        """
        cardinal = Cardinal(self.deterministic)
        decimal = Decimal(self.deterministic)
        cardinal_graph = cardinal.graph_with_and
        graph_decimal_final = decimal.final_graph_wo_negative_w_abbr

        maj_singular_labels = load_labels(
            get_abs_path("english/data/money/currency_major.tsv")
        )
        maj_unit_plural = maj_singular @ SINGULAR_TO_PLURAL
        maj_unit_singular = maj_singular

        graph_maj_singular = insert('currency_maj: "') + maj_unit_singular + insert('"')
        graph_maj_plural = insert('currency_maj: "') + maj_unit_plural + insert('"')

        optional_delete_fractional_zeros = (
            delete(".") + add_weight(delete("0"), -0.2).plus
        ).ques

        graph_integer_one = insert('integer_part: "') + cross("1", "one") + insert('"')
        decimal_delete_last_zeros = (
            (self.DIGIT | delete(",")).star
            + accep(".")
            + self.DIGIT.plus
            + add_weight(delete("0"), -0.01).star
        )
        decimal_with_quantity = self.VSIGMA + self.ALPHA

        graph_decimal = (
            graph_maj_plural
            + insert(" ")
            + (decimal_delete_last_zeros | decimal_with_quantity) @ graph_decimal_final
        )

        graph_integer = (
            insert('integer_part: "')
            + ((self.VSIGMA - "1") @ cardinal_graph)
            + insert('"')
        )  # noqa

        graph_integer_only = graph_maj_singular + insert(" ") + graph_integer_one
        graph_integer_only |= graph_maj_plural + insert(" ") + graph_integer

        final_graph = (
            graph_integer_only + optional_delete_fractional_zeros
        ) | graph_decimal

        self.tagger = self.add_tokens(final_graph.optimize())

    def build_verbalizer(self):
        """
        Finite state transducer for verbalizing money, e.g.
            money { integer_part: "twelve" fractional_part: "o five" currency: "dollars" } -> twelve o five dollars
        """
        decimal = Decimal(self.deterministic)
        keep_space = accep(" ")
        maj = delete('currency_maj: "') + self.NOT_QUOTE.plus + delete('"')

        fractional_part = (
            delete('fractional_part: "') + self.NOT_QUOTE.plus + delete('"')
        )

        integer_part = decimal.integer

        #  *** currency_maj
        graph_integer = integer_part + keep_space + maj

        # *** point *** currency_maj
        graph_decimal = decimal.numbers + keep_space + maj

        graph = graph_integer | graph_decimal

        delete_tokens = self.delete_tokens(graph)
        self.verbalizer = delete_tokens.optimize()
