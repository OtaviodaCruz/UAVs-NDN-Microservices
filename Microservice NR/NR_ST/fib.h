#pragma once

#include <ndn-cxx/interest.hpp>
#include <ndn-cxx/data.hpp>

#include <memory>
#include <list>
#include <unordered_map>
#include <set>

#include "tree/named_tree.h"
#include "fib_entry.h"
#include "network/face.h"

class Fib {
private:
    NamedTree<FibEntry> _tree;
    std::map<std::weak_ptr<Face>, std::vector<ndn::Name>, std::owner_less<std::weak_ptr<Face>>> _faces;

public:
    Fib() = default;

    ~Fib() = default;

    void insert(const std::shared_ptr<Face> &face, const ndn::Name &prefix);

    std::set<std::shared_ptr<Face>> get(const ndn::Name &name);

    void remove(const std::shared_ptr<Face>& face);

    void remove(const std::shared_ptr<Face>& face, const ndn::Name &prefix);

    bool isPrefix(const std::shared_ptr<Face> &face, const ndn::Name &name) const;

    std::string toJSON() const;
};