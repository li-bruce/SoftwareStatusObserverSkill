import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import vue from '@vitejs/plugin-vue';
export default defineConfig({plugins:[react(),vue()],server:{port:8850,strictPort:true}});
