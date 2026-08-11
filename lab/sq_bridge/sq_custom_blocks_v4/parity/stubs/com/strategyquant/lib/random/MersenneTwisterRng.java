package com.strategyquant.lib.random;

/**
 * SQDataLib references this application-only cache RNG during static startup.
 * The ATR harness never calls it; this empty constructor lets the real data
 * series classes initialize in the isolated compile/runtime classpath.
 */
public final class MersenneTwisterRng {
    public MersenneTwisterRng() {}
}
