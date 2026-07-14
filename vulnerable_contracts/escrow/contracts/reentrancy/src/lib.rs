#![no_std]
use soroban_sdk::{contract, contractimpl, token, Address, Env};

#[contract]
pub struct ReentrancyContract;

#[contractimpl]
impl ReentrancyContract {

    pub fn deposit(
        env: Env,
        from: Address,
        token: Address,
        amount: i128
    ) {
        from.require_auth();
        
        // Store balance before transfer
        let current: i128 = env.storage()
            .instance()
            .get(&from)
            .unwrap_or(0);
            
        env.storage().instance().set(&from, &(current + amount));
        
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(&from, &env.current_contract_address(), &amount);
    }

    // VULNERABLE: balance updated AFTER transfer
    // Classic reentrancy pattern
    // Should update state BEFORE making external calls
    pub fn withdraw(
        env: Env,
        to: Address,
        token: Address,
        amount: i128
    ) {
        to.require_auth();
        
        let balance: i128 = env.storage()
            .instance()
            .get(&to)
            .unwrap_or(0);
            
        if balance >= amount {
            // BUG: external call happens BEFORE state update
            // In theory allows reentrancy to drain more than deposited
            let token_client = token::Client::new(&env, &token);
            token_client.transfer(
                &env.current_contract_address(),
                &to,
                &amount
            );
            
            // State updated too late
            env.storage().instance().set(&to, &(balance - amount));
        }
    }

    pub fn get_user_balance(env: Env, user: Address) -> i128 {
        env.storage().instance().get(&user).unwrap_or(0)
    }
}