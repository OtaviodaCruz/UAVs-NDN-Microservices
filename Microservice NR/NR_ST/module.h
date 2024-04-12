/*
Copyright (C) 2015-2018  Xavier MARCHAL
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#pragma once

#include <boost/asio.hpp>
#include <boost/bind.hpp>
#include <boost/thread.hpp>

class Module {
protected:
    size_t _concurrency;
    boost::asio::io_service _ios;
    boost::asio::io_service::work _ios_work;
    boost::thread_group _thread_pool;

public:
    explicit Module(size_t concurrency) : _concurrency(concurrency), _ios(concurrency), _ios_work(_ios) {

    }

    virtual ~Module() = default;

    void start() {
        for (int i = 0; i < _concurrency; ++i) {
            _thread_pool.create_thread(boost::bind(&boost::asio::io_service::run, &_ios));
        }
        _ios.post(boost::bind(&Module::run, this));
    }

    void stop() {
        _ios.stop();
        _thread_pool.join_all();
    }

    virtual void run() = 0;

    const boost::asio::io_service& get_io_service() const {
        return _ios;
    }
};