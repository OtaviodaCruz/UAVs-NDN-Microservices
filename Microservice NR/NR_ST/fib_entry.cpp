#include "fib_entry.h"

FibEntry::FibEntry(const std::shared_ptr<Face> &face) {
    _faces.emplace(face);
}

std::set<std::shared_ptr<Face>> FibEntry::getFaces() {
    std::set<std::shared_ptr<Face>> faces;
    for (const auto& face : _faces) {
        if (auto f = face.lock()) {
            faces.insert(f);
        } else {
            _faces.erase(face);
        }
    }
    return faces;
}

void FibEntry::addFace(const ndn::Name &name, const std::shared_ptr<Face> &face) {
    _faces.emplace(face);
}

void FibEntry::delFace(const std::shared_ptr<Face> &face) {
    _faces.erase(face);
}

bool FibEntry::isValid() const {
    return !_faces.empty();
}

std::string FibEntry::toJSON() {
    std::stringstream ss;
    ss << R"({"faces": [)";
    bool first_face = true;
    auto it = _faces.cbegin();
    while (it != _faces.cend()) {
        if (auto face = it->lock()) {
            if (first_face) {
                first_face = false;
            } else {
                ss << ", ";
            }
            ss << face->getFaceId();
            ++it;
        } else {
            it = _faces.erase(it);
        }
    }
    ss << R"(]})";
    return ss.str();
}