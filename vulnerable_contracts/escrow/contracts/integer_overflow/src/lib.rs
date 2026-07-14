#![no_std]
use soroban_sdk::{contract, contractimpl, token, Address, Env};

#[contract]
pub struct OverflowContract;

#[contractimpl]
impl OverflowContract {

    // VULNERABLE: unchecked multiplication can overflow
    // Attacker passes huge amount that wraps around to small number
    pub fn calculate_fee(
        env: Env,
        amount: i128,
        fee_percent: i128
    ) -> i128 {
        // BUG: should use checked_mul() but uses * instead
        // If amount * fee_percent overflows i128 max value
        // it wraps around to a tiny or negative number
        // attacker pays almost no fee on huge transactions
        amount * fee_percent / 100
    }

    pub fn deposit_with_fee(
        env: Env,
        from: Address,
        token: Address,
        amount: i128,
        fee_percent: i128
    ) {
        from.require_auth();
        
        // Fee calculated using vulnerable function
        let fee = Self::calculate_fee(env.clone(), amount, fee_percent);
        let net_amount = amount - fee;
        
        // Store net amount — attacker manipulates this to be huge
        env.storage().instance().set(&"balance", &net_amount);
        
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(&from, &env.current_contract_address(), &amount);
    }

    pub fn get_balance(env: Env) -> i128 {
        env.storage().instance().get(&"balance").unwrap_or(0)
    }
}