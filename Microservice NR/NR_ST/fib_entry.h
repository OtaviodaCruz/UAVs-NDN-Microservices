#pragma once

#include <ndn-cxx/interest.hpp>

#include <memory>
#include <set>

#include "network/face.h"

class FibEntry {
private:
    std::set<std::weak_ptr<Face>, std::owner_less<std::weak_ptr<Face>>> _faces;

public:
    explicit FibEntry(const std::shared_ptr<Face> &face);

    ~FibEntry() = default;

    std::set<std::shared_ptr<Face>> getFaces();

    void addFace(const ndn::Name &name, const std::shared_ptr<Face> &face);

    void delFace(const std::shared_ptr<Face> &face);

    bool isValid() const;

    std::string toJSON();
};