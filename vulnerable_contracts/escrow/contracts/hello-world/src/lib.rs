#![no_std]
use soroban_sdk::{
    contract,contractimpl,token,Address,Env
};

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    pub fn deposit(
        env: Env,
        from: Address,
        token: Address,
        amount: i128
    ){
        from.require_auth();

        let token_client = token::Client::new(&env, &token);
        token_client.transfer(&from,&env.current_contract_address(),&amount);
    }

    pub fn withdraw(
        env: Env,
        to: Address,
        token: Address,
        amount: i128
    ){

        //require_auth() to be here but kept as a vulnerability

        let token_client = token::Client::new(&env,&token);
        token_client.transfer(&env.current_contract_address(),&to,&amount);
    }

    pub fn balance(
        env: Env,
        token: Address
    ) -> i128{
        let token_client = token::Client::new(&env,&token);
        token_client.balance(&env.current_contract_address())
    }
}

#[cfg(test)]
mod test;
