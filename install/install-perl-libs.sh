#!/usr/bin/env bash

echo -e "\n\nInstalling perl libs\n"

echo "PERL ROOT IN install/install-perl-libs.sh: $PERLBREW_ROOT"

cpanm install Capture::Tiny
cpanm install Mouse
cpanm install Path::Tiny
cpanm install namespace::autoclean
cpanm install DDP
cpanm install YAML::XS
cpanm install Getopt::Long::Descriptive
cpanm install Types::Path::Tiny
cpanm install Sereal # extra MCE performance
cpanm install MCE::Shared
cpanm install List::MoreUtils
cpanm install Log::Fast
cpanm install Parallel::ForkManager
cpanm install Cpanel::JSON::XS
cpanm install Mouse::Meta::Attribute::Custom::Trait::Array
cpanm install Net::HTTP
cpanm install Search::Elasticsearch
cpanm install Search::Elasticsearch::Client::5_0::Direct
cpanm install Math::SigFigs
cpanm install LMDB_File
cpanm install PerlIO::utf8_strict
cpanm install PerlIO::gzip
cpanm install MouseX::SimpleConfig
cpanm install MouseX::ConfigFromFile
# Fails with 5.28.0 for silly reasons related to help print
cpanm install MouseX::Getopt -f 
cpanm install Archive::Extract
cpanm install DBI
# Needed for fetching SQL (Utils::SqlWriter::Connection)
cpanm install DBD::mysql
cpanm install IO/FDPass.pm
cpanm install Beanstalk::Client

cpanm install Math::Round
cpanm install Sys::CpuAffinity

cpanm install Statistics::Distributions
cpanm install File::Which

# Needed for bin/annotate.pl
cpanm install Hash::Merge::Simple
cpanm install Sort::XS
# Custom branch of msgpack-perl that uses latest msgpack-c and
# allows prefer_float32 flag for 5-byte float storage
cpanm install Module::Build::XSUtil
cpanm install Test::LeakTrace
cpanm install Test::Pod

# A dependency of Data::MessagePack installation
cpanm install File::Copy::Recursive

cpanm --uninstall -f Data::MessagePack
rm -rf msgpack-perl
git clone --recursive https://github.com/akotlar/msgpack-perl.git && cd msgpack-perl && git checkout 6fe098dd91e705b12c68d63bcb1f31c369c81e01
perl Build.PL
perl Build test
perl Build install
cd ../ && rm -rf msgpack-perl
