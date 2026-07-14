#![no_std]
use soroban_sdk::{contract, contractimpl, token, Address, Env};

#[contract]
pub struct DrainContract;

#[contractimpl]
impl DrainContract {

    pub fn deposit(
        env: Env,
        from: Address,
        token: Address,
        amount: i128
    ) {
        from.require_auth();
        let token_client = token::Client::new(&env, &token);
        token_client.transfer(&from, &env.current_contract_address(), &amount);
    }

    // VULNERABLE: no ownership check on who can call emergency_withdraw
    // Any address can drain entire contract balance
    // Should check caller is admin/owner first
    pub fn emergency_withdraw(
        env: Env,
        to: Address,
        token: Address
    ) {
        // BUG: missing ownership verification
        // should be: admin.require_auth() where admin is stored owner
        
        let token_client = token::Client::new(&env, &token);
        let balance = token_client.balance(&env.current_contract_address());
        
        if balance > 0 {
            token_client.transfer(
                &env.current_contract_address(),
                &to,
                &balance
            );
        }
    }

    pub fn balance(env: Env, token: Address) -> i128 {
        let token_client = token::Client::new(&env, &token);
        token_client.balance(&env.current_contract_address())
    }
}