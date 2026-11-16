#include <bits/stdc++.h>
using namespace std;

/*
 * Question 2: Word Search Generation
 *
 * Strategy:
 * - Validate and deduplicate the required and forbidden word lists.
 * - Reject cases where a forbidden word is already forced as a substring of a
 *   required word, forwards or backwards.
 * - Choose a filler letter that does not appear in any forbidden word.
 * - Pack required words into separated horizontal rows. The vertical gap and
 *   separator cells prevent forbidden words from being created accidentally.
 */

vector<vector<char>> generate_grid(vector<string> required_words,
                                   vector<string> forbidden_words) {
    if (required_words.empty()) {
        return {};
    }

    sort(required_words.begin(), required_words.end());
    required_words.erase(unique(required_words.begin(), required_words.end()),
                         required_words.end());

    sort(forbidden_words.begin(), forbidden_words.end());
    forbidden_words.erase(unique(forbidden_words.begin(), forbidden_words.end()),
                          forbidden_words.end());

    int max_word = 0;
    int max_forbidden = 0;
    bool used_in_forbidden[26] = {};

    for (const string& word : required_words) {
        if (word.empty()) {
            return {};
        }
        for (char c : word) {
            if (c < 'A' || c > 'Z') {
                return {};
            }
        }
        max_word = max(max_word, (int)word.size());
    }

    for (const string& word : forbidden_words) {
        if (word.empty()) {
            return {};
        }
        max_forbidden = max(max_forbidden, (int)word.size());
        for (char c : word) {
            if (c < 'A' || c > 'Z') {
                return {};
            }
            used_in_forbidden[c - 'A'] = true;
        }
    }

    for (const string& forbidden : forbidden_words) {
        string reversed = forbidden;
        reverse(reversed.begin(), reversed.end());

        for (const string& required : required_words) {
            if (required.find(forbidden) != string::npos ||
                required.find(reversed) != string::npos) {
                return {};
            }
        }
    }

    char filler = '?';
    for (char c = 'A'; c <= 'Z'; c++) {
        if (!used_in_forbidden[c - 'A']) {
            filler = c;
            break;
        }
    }
    if (filler == '?') {
        return {};
    }

    const bool needs_separator = !forbidden_words.empty();
    const int gap = max(1, max_forbidden);
    const int word_count = (int)required_words.size();

    vector<int> order(word_count);
    iota(order.begin(), order.end(), 0);

    auto item_size = [&](int i) -> long long {
        return (long long)required_words[i].size() + (needs_separator ? 1 : 0);
    };

    sort(order.begin(), order.end(), [&](int a, int b) {
        return item_size(a) > item_size(b);
    });

    long long total = 0;
    for (int i : order) {
        total += item_size(i);
    }

    long long side = max((long long)max_word + (needs_separator ? 1 : 0),
                         (long long)gap);
    side = max(side, (long long)ceil(sqrt((double)total * gap)));

    vector<vector<int>> bins;
    multiset<pair<long long, int>> remaining_width;

    for (int word_index : order) {
        long long width = item_size(word_index);
        auto it = remaining_width.lower_bound({width, -1});

        if (it == remaining_width.end()) {
            int id = (int)bins.size();
            bins.push_back({word_index});
            remaining_width.insert({side - width, id});
        } else {
            long long space = it->first;
            int id = it->second;
            remaining_width.erase(it);
            bins[id].push_back(word_index);
            remaining_width.insert({space - width, id});
        }
    }

    side = max(side, (long long)bins.size() * gap);
    if (side > 10000) {
        return {};
    }

    int n = (int)side;
    vector<vector<char>> grid(n, vector<char>(n, filler));

    for (int r = 0; r < (int)bins.size(); r++) {
        int row = r * gap;
        int col = 0;

        for (int word_index : bins[r]) {
            const string& word = required_words[word_index];
            for (char c : word) {
                grid[row][col++] = c;
            }
            if (needs_separator) {
                col++;
            }
        }
    }

    return grid;
}

static string ltrim(const string& str) {
    size_t start = str.find_first_not_of(" \t\n\r");
    if (start == string::npos) {
        return "";
    }
    return str.substr(start);
}

static string rtrim(const string& str) {
    size_t end = str.find_last_not_of(" \t\n\r");
    if (end == string::npos) {
        return "";
    }
    return str.substr(0, end + 1);
}

int main() {
    string required_words_count_temp;
    getline(cin, required_words_count_temp);

    int required_words_count = stoi(ltrim(rtrim(required_words_count_temp)));
    vector<string> required_words(required_words_count);
    for (int i = 0; i < required_words_count; i++) {
        getline(cin, required_words[i]);
        required_words[i] = rtrim(ltrim(required_words[i]));
    }

    string forbidden_words_count_temp;
    getline(cin, forbidden_words_count_temp);

    int forbidden_words_count = stoi(ltrim(rtrim(forbidden_words_count_temp)));
    vector<string> forbidden_words(forbidden_words_count);
    for (int i = 0; i < forbidden_words_count; i++) {
        getline(cin, forbidden_words[i]);
        forbidden_words[i] = rtrim(ltrim(forbidden_words[i]));
    }

    vector<vector<char>> result = generate_grid(required_words, forbidden_words);

    for (const auto& row : result) {
        for (char c : row) {
            cout << c;
        }
        cout << '\n';
    }

    return 0;
}
