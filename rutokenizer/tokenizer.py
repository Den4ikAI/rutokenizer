# -*- coding: utf-8 -*-
'''
Простые токенизаторы - разбивают строку на слова, учтывая наличие многословных лексем.
'''

from __future__ import print_function

import re
import codecs
import itertools
import pathlib
import os
import pickle
import gzip


class Tokenizer(object):
    """
    Базовый токенизатор для более-менее чистых русскоязычных текстов.
    Учитываются русские многословные лексемы ("что-либо", "по-японски").
    """
    def __init__(self):
        self.regex1 = re.compile(u'[%s ]+' % re.escape(u'\t\u00a0\u202F\u2060\u200A\s'))
        self.delimiters = re.compile(u'([%s])' % re.escape(u'‼≠™®•·[¡+<>`~;.,‚?!-…№”“„{}|‹›/\'"–—_:‑«»*]()‘’≈'))
        self.spaces = re.compile(u'[%s]+' % re.escape(u' \u00a0\u202F\u2060\u200A'))
        self.delimiters2 = re.compile(u'([%s])' % re.escape(u' \u00a0\u202F\u2060\u200A‼≠™®•·[¡+<>`~;.,‚?!-…‑№”“„{}|‹›/\'"–—_:«»*]()‘’≈'))
        self.words_with_hyphen = None
        self.prefix_hyphen = None

    def load(self):
        module_folder = str(pathlib.Path(__file__).resolve().parent)
        p = os.path.join(module_folder, 'rutokenizer.dat')

        with gzip.open(p, 'r') as f:
            data = pickle.load(f)
            self.words_with_hyphen = data['words_with_hyphen']
            self.prefix_hyphen = data['prefix_hyphen']

        pass

    def before_split(self, s):
        return self.delimiters.sub(u' \\1 ', s.replace('--', '-'))

    def tokenize0(self, phrase):
        return list(w for w in self.regex1.split(self.before_split(phrase)) if len(w) > 0)

    def tokenize(self, phrase):
        """
        Простая токенизация, без сохранения информации о посимвольных позициях токенов.
        :param phrase: юникодная строка разбираемого текста
        :return: список токенов, каждый токен - юникодная строка
        """
        tokens0 = self.tokenize0(phrase)
        tokens1 = []
        nt = len(tokens0)
        i = 0
        while i < nt:
            utoken0 = tokens0[i].lower()
            if utoken0 not in self.prefix_hyphen:
                tokens1.append(tokens0[i])
                i += 1
            else:
                min_len, max_len = self.prefix_hyphen[utoken0]
                found_aggregate = False
                for l1 in range(max_len, min_len-1, -1):
                    if i + l1 < nt:
                        aggregate = u''.join(tokens0[i: i + l1 + 2])
                        if aggregate.lower() in self.words_with_hyphen:
                            tokens1.append(aggregate)
                            i += l1 + 2
                            found_aggregate = True
                            break

                if not found_aggregate:
                    tokens1.append(tokens0[i])
                    i += 1

        return tokens1

    def is_space(self, s):
        return self.spaces.match(s)

    def tokenize2(self, phrase):
        """
        Разбор строки на токены с возвратом посимвольных позиций токенов
        :param phrase: юникодная строка разбираемого текста
        :return: список кортежей (юникодная_строка, начальная_позиция, конечная_позиция+1)
        """

        # Сначала предварительная разбивка на токены
        # Для этого найдем позиции символов-разделителей
        tokens0 = []
        mx = self.delimiters2.finditer(phrase)
        delim_tokens = []
        for m in mx:
            delim_tokens.append((m.group(0), m.start(), m.end()))

        for i, delim in enumerate(delim_tokens):
            if i > 0:
                # Токен между предыдущим и текущим разделителями
                prev_delim = delim_tokens[i-1]
                if prev_delim[2] != delim[1]:
                    prev_token_start = prev_delim[2]
                    prev_token_end = delim[1]
                    prev_token = phrase[prev_token_start: prev_token_end]
                    tokens0.append((prev_token, prev_token_start, prev_token_end))
            elif delim[1] > 0:
                # Токен от начала строки до текущего разделителя
                prev_token_start = 0
                prev_token_end = delim[1]
                prev_token = phrase[prev_token_start: prev_token_end]
                tokens0.append((prev_token, prev_token_start, prev_token_end))

            if not self.is_space(delim[0]):
                tokens0.append(delim)

        # последний токен, если это не разделитель, надо добавить.
        phrase_len = len(phrase)
        if len(delim_tokens) == 0 or delim_tokens[-1][2] != phrase_len:
            start_pos = delim_tokens[-1][2] if len(delim_tokens) > 0 else 0
            last_token = (phrase[start_pos:], start_pos, phrase_len)
            tokens0.append(last_token)


        # Теперь надо объединить MWU типа "что-либо"
        tokens1 = []
        nt = len(tokens0)
        i = 0
        while i < nt:
            utoken0 = tokens0[i][0].lower()
            if utoken0 not in self.prefix_hyphen:
                tokens1.append(tokens0[i])
                i += 1
            else:
                min_len, max_len = self.prefix_hyphen[utoken0]
                found_aggregate = False
                for l1 in range(max_len, min_len-1, -1):
                    if i + l1 < nt:
                        aggregate = u''.join(t[0] for t in tokens0[i: i + l1 + 2])
                        if aggregate.lower() in self.words_with_hyphen:
                            compound_token = (aggregate, tokens0[i][1], tokens0[i + l1 + 1][2])
                            tokens1.append(compound_token)
                            i += l1 + 2
                            found_aggregate = True
                            break

                if not found_aggregate:
                    tokens1.append(tokens0[i])
                    i += 1

        return tokens1


def tokenizer_tests():
    tokenizer = Tokenizer()
    tokenizer.load()

    # Символ 0x00a0 в качестве пробельного разделителя
    predicted = tokenizer.tokenize(u'галактики — ')
    assert(predicted[0] == u'галактики')
    assert(predicted[1] == u'—')

    # Суррогатный пробел \x200a в кач-ве разделителя
    predicted = tokenizer.tokenize(u'чуть что — бежит в обменник.')
    assert (len(predicted) == 7)
    predicted = u'|'.join(predicted)
    expected = u'чуть|что|—|бежит|в|обменник|.'
    if predicted != expected:
        print(u'Failed: predicted={} expected={}'.format(predicted, expected))
        raise AssertionError()


    # Символ "‑" в качестве разделителя
    predicted = tokenizer.tokenize(u'книга‑то')
    assert(len(predicted) == 3)
    assert(predicted[0] == u'книга')
    assert(predicted[1] == u'‑')
    assert(predicted[2] == u'то')

    predicted = u'|'.join(tokenizer.tokenize(u'По-доброму вышел из-за угла, уйди-ка куда-нибудь. Потому что ярко-зеленый.'))
    expected = u'По-доброму|вышел|из-за|угла|,|уйди|-|ка|куда-нибудь|.|Потому|что|ярко-зеленый|.'
    assert(predicted == expected)

    # проверка токенизации с сохранением посимвольных позиций
    predicted = tokenizer.tokenize2(u'Я  сплю, мечтаю-ка  что-либо.')
    assert(len(predicted) == 8)
    s = u'|'.join(t[0] for t in predicted)
    assert(s == u'Я|сплю|,|мечтаю|-|ка|что-либо|.')
    assert(predicted[0] == (u'Я', 0, 1))
    assert(predicted[6] == (u'что-либо', 20, 28))
    assert(predicted[7] == (u'.', 28, 29))

    # Последний токен не является разделителем
    predicted = tokenizer.tokenize2(u'Я  сплю, мечтаю-ка  что-либо')
    assert(predicted[6] == (u'что-либо', 20, 28))

    # В предложении всего один токен
    predicted = tokenizer.tokenize2(u'кошки')
    assert(predicted[0] == (u'кошки', 0, 5))

    print('Tokenizer tests - PASSED OK.')


if __name__ == '__main__':
    tokenizer_tests()

    tokenizer = Tokenizer()
    tokenizer.load()
    res = tokenizer.tokenize(u'По-доброму вышел из-за угла, уйди-ка куда-нибудь. Потому что ярко-зеленый.')
    print('|'.join(res))
