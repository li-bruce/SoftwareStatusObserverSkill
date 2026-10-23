<script setup lang="ts">
import {ref,watchEffect} from 'vue';
const props=defineProps<{run:(event:string)=>string,bo_observe?:Function}>();
const state=ref('pending');
watchEffect(()=>{try {props.bo_observe?.('vue.template','read',{inputs:{has_handler:typeof props.run==='function'},outputs:{state:state.value}});} catch {}});
function start(){state.value=props.run('start');}
function finish(){state.value=props.run('finish');}
</script>
<template><section><h2>Vue task</h2><p data-testid="vue-state">{{state}}</p><button @click="start">Start Vue task</button><button @click="finish">Finish Vue task</button></section></template>
