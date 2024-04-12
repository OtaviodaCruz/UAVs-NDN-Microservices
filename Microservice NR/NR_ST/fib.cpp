#include "fib.h"

void Fib::insert(const std::shared_ptr<Face> &face, const ndn::Name &prefix) {
    if (auto entry = _tree.find(prefix)) {
        return entry->addFace(prefix, face);
    } else {
        _tree.insert(prefix, std::make_shared<FibEntry>(face));
    }

    auto it = _faces.find(face);
    if (it != _faces.end()) {
        it->second.emplace_back(prefix);
    } else {
        _faces.emplace(face, std::vector<ndn::Name>{prefix});
    }
}

std::set<std::shared_ptr<Face>> Fib::get(const ndn::Name &name) {
    std::set<std::shared_ptr<Face>> faces;
    auto list = _tree.findAllUntil(name);
    for (auto& element : list) {
        auto &&entry_faces = element.second->getFaces();
        faces.insert(std::make_move_iterator(entry_faces.begin()), std::make_move_iterator(entry_faces.end()));
    }
    return faces;
}

void Fib::remove(const std::shared_ptr<Face> &face) {
    auto it = _faces.find(face);
    if (it != _faces.end()) {
        for (const auto& name : it->second) {
            _tree.remove(name);
        }
        _faces.erase(it);
    }
}

void Fib::remove(const std::shared_ptr<Face> &face, const ndn::Name &prefix) {
    auto it = _tree.find(prefix);
    it->delFace(face);
}

bool Fib::isPrefix(const std::shared_ptr<Face> &face, const ndn::Name &name) const {
    auto list = _tree.findAllUntil(name);
    for (const auto& element : list) {
        const auto &entry_faces = element.second->getFaces();
        if (entry_faces.find(face) != entry_faces.end()) {
            return true;
        }
    }
    return false;
}

std::string Fib::toJSON() const {
    return _tree.toJSON();
}