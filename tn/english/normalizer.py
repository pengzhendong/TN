# Copyright (c) 2022 Zhendong Peng (pzd17@tsinghua.org.cn)
# Copyright (c) 2024 Xingchen Song (sxc19@tsinghua.org.cn)
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

from tn.processor import Processor
from tn.english.rules.cardinal import Cardinal
from tn.english.rules.ordinal import Ordinal
from tn.english.rules.word import Word

from pynini.lib.pynutil import add_weight, delete
from importlib_resources import files


class Normalizer(Processor):

    def __init__(self, cache_dir=None, overwrite_cache=False):
        super().__init__(name='en_normalizer')
        if cache_dir is None:
            cache_dir = files("tn")
        self.build_fst('en_tn', cache_dir, overwrite_cache)

    def build_tagger(self):
        cardinal = add_weight(Cardinal().tagger, 1.0)
        ordinal = add_weight(Ordinal().tagger, 1.0)
        word = add_weight(Word().tagger, 100)
        tagger = (cardinal | ordinal | word).optimize() + self.DELETE_SPACE
        # delete the last space
        self.tagger = tagger.star @ self.build_rule(delete(' '), r='[EOS]')

    def build_verbalizer(self):
        cardinal = Cardinal().verbalizer
        ordinal = Ordinal().verbalizer
        word = Word().verbalizer
        verbalizer = (cardinal | ordinal | word).optimize() + self.INSERT_SPACE
        self.verbalizer = verbalizer.star
