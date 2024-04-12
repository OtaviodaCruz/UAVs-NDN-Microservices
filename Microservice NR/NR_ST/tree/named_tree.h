#pragma once

#include <ndn-cxx/name.hpp>

#include <memory>
#include <map>
#include <stack>

template <class T>
class NamedTree {
private:
    class NamedNode : public std::enable_shared_from_this<NamedNode> {
    private:
        NamedTree<T> &_tree;

        const ndn::Name _name;
        const std::weak_ptr<NamedNode> _parent;
        std::map<ndn::Name::Component, std::weak_ptr<NamedNode>> _children;

        mutable std::shared_ptr<T> _value;

    public:
        NamedNode(NamedTree<T> &tree, ndn::Name name, const std::shared_ptr<NamedNode> &parent)
                : _tree(tree)
                , _name(std::move(name))
                , _parent(parent) {

        }

        ~NamedNode() = default;

        const ndn::Name& getName() const {
            return _name;
        }

        std::shared_ptr<NamedNode> getParent() const {
            return _parent.lock();
        }

        bool hasChildren() const {
            return !_children.empty();
        }

        std::shared_ptr<NamedNode> getChild(const ndn::Name::Component &name_component) {
            auto it = _children.find(name_component);
            if (it != _children.end()) {
                if (auto ptr = it->second.lock()) {
                    return ptr;
                } else {
                    _children.erase(it);
                    return nullptr;
                }
            } else {
                return nullptr;
            }
        }

        std::shared_ptr<NamedNode> getLeftChild() {
            auto it = _children.begin();
            if (it != _children.end()) {
                if (auto ptr = it->second.lock()) {
                    return ptr;
                } else {
                    _children.erase(it);
                    return nullptr;
                }
            } else {
                return nullptr;
            }
        }

        std::shared_ptr<NamedNode> getRightChild() {
            auto it = _children.rbegin();
            if (it != _children.rend()) {
                if (auto ptr = it->second.lock()) {
                    return ptr;
                } else {
                    _children.erase(it);
                    return nullptr;
                }
            } else {
                return nullptr;
            }
        }

        std::vector<std::shared_ptr<NamedNode>> getChildren() {
            std::vector<std::shared_ptr<NamedNode>> children(_children.size());
            for (const auto& child : _children) {
                if (auto c = child->second.lock()) {
                    children.emplace_back(c);
                } else {
                    children.erase(child);
                }
            }
            return children;
        }

        std::pair<bool, std::shared_ptr<NamedNode>> tryCreateEmptyChild(const ndn::Name::Component &name_component) {
            ndn::Name name(_name);
            name.append(name_component);
            auto result = _tree._nodes.emplace(name, std::make_shared<NamedNode>(_tree, name, this->shared_from_this()));
            if (result.second) {
                _children.emplace(name_component, result.first->second);
            }
            return {result.second, result.first->second};
        }

        bool addChild(const std::shared_ptr<NamedNode> &node) {
            return _name.getPrefix(-1) == node->getName() && _children.emplace(node->getName().get(-1), node).second;
        }

        void delChild(const ndn::Name::Component &name_component) {
            _children.erase(name_component);
        }

        bool hasValue() const {
            return _value != nullptr;
        }

        std::shared_ptr<T> getValue() const {
            return _value;
        }

        void setValue(const std::shared_ptr<T> &value) const {
            _value = value;
        }

        void clearValue() const {
            _value.reset();
        }

        bool isValid() const {
            // _parent.expired() == 0 only for root
            return !_children.empty() || _value || _parent.expired();
        }

        std::string toJSON() {
            std::stringstream ss;
            ss << R"({"name":")" << _name << R"(", "info":)" << (_value ? _value->toJSON() : "{}") << R"(, "children":[)";
            bool first_child = true;
            auto it = _children.cbegin();
            while (it != _children.cend()) {
                if (auto child = it->second.lock()) {
                    if (first_child) {
                        first_child = false;
                    } else {
                        ss << ", ";
                    }
                    ss << child->toJSON();
                    ++it;
                } else {
                    it = _children.erase(it);
                }
            }
            ss << "]}";
            return ss.str();
        }
    };

    size_t _populated_nodes = 0;

    std::shared_ptr<NamedNode> _root;
    std::map<ndn::Name, std::shared_ptr<NamedNode>> _nodes;

public:
    NamedTree() {
        _root = std::make_shared<NamedNode>(*this, "/", nullptr);
        _nodes.emplace("/", _root);
    }

    ~NamedTree() = default;

    size_t size() const {
        return _nodes.size();
    }

    size_t getPopulatedNodes() {
        return _populated_nodes;
    }

    std::shared_ptr<T> find(const ndn::Name &name) const {
        auto it = _nodes.find(name);
        return it != _nodes.end() ? it->second->getValue() : nullptr;
    }

    std::pair<ndn::Name, std::shared_ptr<T>> findLastUntil(const ndn::Name &name) const {
        auto node = _root;
        auto value = _root->getValue();
        for (const auto& component : name) {
            if (const auto& child = node->getChild(component)) {
                if (child->hasValue()) {
                    value = child->getValue();
                }
                node = child;
            } else {
                break;
            }
        }
        return {node->getName(), value};
    }

    std::vector<std::pair<ndn::Name, std::shared_ptr<T>>> findAllUntil(const ndn::Name &name) const {
        std::vector<std::pair<ndn::Name, std::shared_ptr<T>>> values;
        if (_root->hasValue()) {
            values.emplace_back(_root->getName(), _root->getValue());
        }
        auto node = _root;
        for (const auto& component : name) {
            if (const auto& child = node->getChild(component)) {
                if (child->hasValue()) {
                    values.emplace_back(child->getName(), child->getValue());
                }
                node = child;
            } else {
                break;
            }
        }
        return values;
    }

    std::pair<ndn::Name, std::shared_ptr<T>> findFirstFrom(const ndn::Name &name, bool rightmost = false) const {
        auto it = _nodes.find(name);
        if (it == _nodes.end()) {
            return {ndn::Name(), nullptr};
        }

        std::shared_ptr<NamedNode> node = it->second;
        if (node->hasValue()) {
            return {node->getName(), node->getValue()};
        }
        node = rightmost ? node->getRightChild() : node->getLeftChild();
        if (node) {
            do {
                if (node->hasValue()) {
                    return {node->getName(), node->getValue()};
                }
            } while (node = node->getLeftChild());
        }
    }

    std::vector<std::pair<ndn::Name, std::shared_ptr<T>>> findAllFrom(const ndn::Name &name) const {
        std::vector<std::pair<ndn::Name, std::shared_ptr<T>>> values;
        auto it = _nodes.find(name);
        if (it == _nodes.end()) {
            return values;
        }

        std::stack<std::shared_ptr<NamedNode>> node_stack;
        node_stack.emplace(it->second);
        while (!node_stack.empty()) {
            std::shared_ptr<NamedNode> node = node_stack.top();
            values.emplace_back(node->getName(), node->getValue());
            node_stack.pop();
            for (const auto& child : node->getChildren()) {
                node_stack.emplace(child);
            }
        }
        return values;
    }

    void insert(const ndn::Name &name, const std::shared_ptr<T> &value, bool replace = false) {
        auto it = _nodes.find(name);
        if (it == _nodes.end()) {
            auto node = _root;
            for (const auto& component : name) {
                node = node->tryCreateEmptyChild(component).second;
            }
            node->setValue(value);
            ++_populated_nodes;
        } else {
            if (!it->second->hasValue()) {
                it->second->setValue(value);
                ++_populated_nodes;
            } else if(replace) {
                it->second->setValue(value);
            }
        }
    }

    void remove(const ndn::Name &name) {
        auto it = _nodes.find(name);
        if (it == _nodes.end()) {
            return;
        }
        std::shared_ptr<NamedNode> node = it->second;
        node->clearValue();
        --_populated_nodes;

        while(!node->isValid()) {
            auto parent = node->getParent();
            _nodes.erase(node->getName());
            parent->delChild(node->getName().get(-1));
            node = parent;
        }
    }

    std::string toJSON() const {
        return _root->toJSON();
    }
};